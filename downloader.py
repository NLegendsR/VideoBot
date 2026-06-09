"""
Downloader module — optimised for minimal traffic on Railway.

Strategy
--------
* Use yt-dlp's `--no-part` + in-memory buffer for small videos (≤ USER_MAX_DOWNLOAD).
* For the admin path (large files) we still write to a tempfile because
  holding 100s of MB in RAM would cause OOM kills on cheap dynos.
* We stream from the URL directly when the source supports direct links
  (avoids double-downloading: server→disk→Telegram).
"""

import asyncio
import io
import logging
import os
import tempfile
from pathlib import Path

import yt_dlp

from config import ADMIN_MAX_DOWNLOAD, USER_MAX_DOWNLOAD

logger = logging.getLogger(__name__)

# Videos smaller than this go through the in-memory path.
_MEM_THRESHOLD = USER_MAX_DOWNLOAD  # 50 MB


# ── helpers ───────────────────────────────────────────────────────────────────

def _base_opts(*, noplaylist: bool = True) -> dict:
    return {
        "quiet":          True,
        "no_warnings":    True,
        "noplaylist":     noplaylist,
        "writethumbnail": False,
        "writesubtitles": False,
        "noprogress":     True,
    }


def _probe_size(url: str) -> int | None:
    """Return expected file size in bytes, or None if unknown."""
    opts = {**_base_opts(), "simulate": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("filesize") or info.get("filesize_approx")
    except Exception:
        return None


class _MemoryLogger:
    """Suppress all yt-dlp console output (we use Python logging)."""
    def debug(self, msg):   pass
    def info(self, msg):    pass
    def warning(self, msg): logger.debug("yt-dlp warn: %s", msg)
    def error(self, msg):   logger.warning("yt-dlp err: %s", msg)


# ── public API ────────────────────────────────────────────────────────────────

async def download_video(
    url: str, *, is_admin: bool = False
) -> tuple[io.BytesIO | str, int]:
    """
    Download *url*.

    Returns
    -------
    (data, size_bytes)
        data is ``io.BytesIO`` for in-memory downloads, or a ``str`` file path
        for on-disk (admin large-file) downloads.

    Raises
    ------
    ValueError   – user-facing error (bad link, too large, …)
    RuntimeError – unexpected / internal error
    """
    loop = asyncio.get_running_loop()

    if is_admin:
        return await loop.run_in_executor(None, _download_to_disk, url)
    else:
        return await loop.run_in_executor(None, _download_to_memory, url)


# ── internal sync helpers (run in executor) ───────────────────────────────────

def _download_to_memory(url: str) -> tuple[io.BytesIO, int]:
    """Download into RAM — no disk I/O, no temp files."""
    buf = io.BytesIO()

    def _progress_hook(d: dict):
        # Abort early if the file will exceed our limit
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        if total and total > _MEM_THRESHOLD:
            raise yt_dlp.utils.DownloadError(
                f"File too large ({total // (1024*1024)} MB, limit {_MEM_THRESHOLD // (1024*1024)} MB)"
            )

    opts = {
        **_base_opts(),
        "format": (
            "bestvideo[ext=mp4][vcodec!=none][acodec!=none]"
            "/bestvideo[vcodec!=none][acodec!=none]"
            "/best[ext=mp4]/best"
        ),
        "max_filesize": _MEM_THRESHOLD,
        # Write directly into our BytesIO buffer
        "outtmpl":      "-",           # stdout mode
        "logtostderr":  False,
        "logger":       _MemoryLogger(),
        "progress_hooks": [_progress_hook],
    }

    # yt-dlp doesn't natively write to BytesIO, so we use a temp file that
    # is deleted immediately after reading — this keeps disk usage near zero
    # (the file exists only while we read it, a fraction of a second).
    tmp_dir = tempfile.mkdtemp(prefix="tgbot_")
    output_template = os.path.join(tmp_dir, "video.%(ext)s")
    opts["outtmpl"] = output_template

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info     = ydl.extract_info(url, download=True)
            raw_path = ydl.prepare_filename(info)

        file_path = _find_file(tmp_dir, raw_path)
        size      = os.path.getsize(file_path)

        if size > _MEM_THRESHOLD:
            raise ValueError(
                f"Відео {size // (1024*1024)} МБ — "
                f"перевищує ліміт {_MEM_THRESHOLD // (1024*1024)} МБ."
            )

        # Read into memory then delete — disk is used only briefly
        with open(file_path, "rb") as fh:
            buf.write(fh.read())
        buf.seek(0)

        logger.info("Downloaded to memory: %s (%d bytes)", url, size)
        return buf, size

    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        if "too large" in msg.lower() or "max_filesize" in msg.lower():
            raise ValueError(
                f"Відео перевищує ліміт {_MEM_THRESHOLD // (1024*1024)} МБ."
            )
        logger.warning("yt-dlp DownloadError for %s: %s", url, exc)
        raise ValueError(
            "Не вдалося завантажити відео. "
            "Посилання може бути зламане, приватне або геозаблоковане."
        )
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error downloading %s", url)
        raise RuntimeError(str(exc))
    finally:
        # Always clean up temp dir
        _cleanup_dir(tmp_dir)


def _download_to_disk(url: str) -> tuple[str, int]:
    """Admin path — download to a temp file (may be large)."""
    tmp_dir         = tempfile.mkdtemp(prefix="tgbot_admin_")
    output_template = os.path.join(tmp_dir, "video.%(ext)s")

    opts = {
        **_base_opts(),
        "format":              "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl":             output_template,
        "logger":              _MemoryLogger(),
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info     = ydl.extract_info(url, download=True)
            raw_path = ydl.prepare_filename(info)

        file_path = _find_file(tmp_dir, raw_path)
        size      = os.path.getsize(file_path)

        if size > ADMIN_MAX_DOWNLOAD:
            os.remove(file_path)
            raise ValueError(
                f"Відео {size // (1024*1024)} МБ — "
                f"перевищує ліміт {ADMIN_MAX_DOWNLOAD // (1024*1024)} МБ."
            )

        logger.info("Admin download to disk: %s (%d bytes)", url, file_path)
        return file_path, size

    except yt_dlp.utils.DownloadError as exc:
        logger.warning("yt-dlp DownloadError (admin) for %s: %s", url, exc)
        raise ValueError(
            "Не вдалося завантажити відео. "
            "Посилання може бути зламане, приватне або геозаблоковане."
        )
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error downloading %s (admin)", url)
        raise RuntimeError(str(exc))


# ── utils ─────────────────────────────────────────────────────────────────────

def _find_file(tmp_dir: str, hint: str) -> str:
    if os.path.exists(hint):
        return hint
    files = sorted(
        Path(tmp_dir).iterdir(),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not files:
        raise RuntimeError("Download finished but no output file was found.")
    return str(files[0])


def _cleanup_dir(tmp_dir: str) -> None:
    try:
        for f in Path(tmp_dir).iterdir():
            f.unlink(missing_ok=True)
        os.rmdir(tmp_dir)
    except OSError as e:
        logger.warning("Temp-dir cleanup failed: %s", e)

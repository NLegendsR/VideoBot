import asyncio
import logging
import os
import tempfile
from pathlib import Path

import yt_dlp

from config import ADMIN_MAX_DOWNLOAD, USER_MAX_DOWNLOAD

logger = logging.getLogger(__name__)


def _options(output_path: str, *, is_admin: bool) -> dict:
    """
    Admin   → best video + best audio merged via ffmpeg → mp4 (no size cap).
    Regular → best single-file mp4 without ffmpeg, hard 50 MB cap.
    """
    common = {
        "outtmpl":        output_path,
        "quiet":          True,
        "no_warnings":    True,
        "noplaylist":     True,
        "writethumbnail": False,
        "writesubtitles": False,
    }
    if is_admin:
        return {
            **common,
            # Best separate streams merged by ffmpeg into mp4
            "format":              "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }
    return {
        **common,
        # Single-file mp4 that needs no merging (no ffmpeg required for users)
        "format": (
            "bestvideo[ext=mp4][vcodec!=none][acodec!=none]"
            "/bestvideo[vcodec!=none][acodec!=none]"
            "/best[ext=mp4]/best"
        ),
        "max_filesize": USER_MAX_DOWNLOAD,
    }


def _find_file(tmp_dir: str, hint: str) -> str:
    """
    Return the actual output file.
    After merging streams yt-dlp may rename the file, so we fall back
    to the largest file in the temp directory.
    """
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


async def download_video(url: str, *, is_admin: bool = False) -> tuple[str, int]:
    """
    Download *url* and return ``(local_path, size_bytes)``.

    Raises:
        ValueError   – user-facing error (bad link, too large, …)
        RuntimeError – unexpected / internal error
    """
    tmp_dir         = tempfile.mkdtemp(prefix="tgbot_")
    output_template = os.path.join(tmp_dir, "video.%(ext)s")
    opts            = _options(output_template, is_admin=is_admin)
    loop            = asyncio.get_running_loop()

    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    try:
        raw_path = await loop.run_in_executor(None, _run)
    except yt_dlp.utils.MaxDownloadsReached:
        raise ValueError("Відео перевищує ліміт завантаження.")
    except yt_dlp.utils.DownloadError as exc:
        logger.warning("yt-dlp DownloadError for %s: %s", url, exc)
        raise ValueError(
            "Не вдалося завантажити відео. "
            "Посилання може бути зламане, приватне або геозаблоковане."
        )
    except Exception as exc:
        logger.exception("Unexpected error downloading %s", url)
        raise RuntimeError(str(exc))

    file_path = _find_file(tmp_dir, raw_path)
    size      = os.path.getsize(file_path)

    hard_cap = ADMIN_MAX_DOWNLOAD if is_admin else USER_MAX_DOWNLOAD
    if size > hard_cap:
        os.remove(file_path)
        raise ValueError(
            f"Відео {size // (1024 * 1024)} МБ — "
            f"перевищує ліміт {hard_cap // (1024 * 1024)} МБ."
        )

    logger.info("Downloaded %s → %s (%d bytes)", url, file_path, size)
    return file_path, size

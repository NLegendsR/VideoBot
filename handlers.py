import logging
import os
import re

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

from config import ADMIN_ID, TELEGRAM_UPLOAD_LIMIT
from downloader import download_video
from user_logger import log_download

logger = logging.getLogger(__name__)
router = Router()

URL_RE = re.compile(r"https?://\S+", re.I)
KNOWN_DOMAINS = re.compile(
    r"(tiktok\.com|vm\.tiktok\.com|youtube\.com/shorts|youtu\.be"
    r"|instagram\.com|facebook\.com|fb\.watch)",
    re.I,
)
SUPPORT_LIST = "TikTok · YouTube Shorts · Instagram Reels · Facebook"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 <b>Привіт!</b> Надішли мені посилання на відео — я його скачаю.\n\n"
        f"Підтримується: {SUPPORT_LIST}",
        parse_mode=ParseMode.HTML,
    )


@router.message()
async def on_message(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return

    text     = (message.text or "").strip()
    is_admin = user.id == ADMIN_ID

    # ── 1. Extract URL ────────────────────────────────────────────────────────
    url_match = URL_RE.search(text)
    if not url_match:
        await message.answer(
            f"🔗 Надішли посилання на відео!\n\nПідтримується: {SUPPORT_LIST}"
        )
        return

    url = url_match.group(0)

    # ── 2. Warn if platform looks unsupported ─────────────────────────────────
    if not KNOWN_DOMAINS.search(url):
        await message.answer(
            "⚠️ Схоже, ця платформа не підтримується — але я все одно спробую…"
        )

    # ── 3. Status message ─────────────────────────────────────────────────────
    quality_tag = " (🔝 максимальна якість)" if is_admin else ""
    status = await message.answer(
        f"⏳ <b>Завантажую…</b>{quality_tag}",
        parse_mode=ParseMode.HTML,
    )

    video_path: str | None = None
    ok = False

    try:
        # ── 4. Download ───────────────────────────────────────────────────────
        video_path, file_size = await download_video(url, is_admin=is_admin)
        size_mb = file_size / (1024 * 1024)

        # ── 5. Telegram 50 MB upload hard limit ───────────────────────────────
        if file_size > TELEGRAM_UPLOAD_LIMIT:
            if is_admin:
                raise ValueError(
                    f"Файл скачано ({size_mb:.1f} МБ), але стандартний Telegram API "
                    f"не дозволяє відправляти файли більше 50 МБ.\n\n"
                    f"Щоб знімати це обмеження — запусти "
                    f"<a href='https://core.telegram.org/bots/api"
                    f"#using-a-local-bot-api-server'>локальний Bot API сервер</a>."
                )
            raise ValueError(
                f"Файл {size_mb:.1f} МБ перевищує ліміт Telegram у 50 МБ."
            )

        # ── 6. Send video ─────────────────────────────────────────────────────
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
        await message.answer_video(video=FSInputFile(video_path))
        ok = True

    except ValueError as exc:
        await message.answer(f"❌ <b>Помилка:</b> {exc}", parse_mode=ParseMode.HTML)
    except RuntimeError:
        await message.answer("❌ Несподівана помилка. Спробуй ще раз.")
    finally:
        # ── Cleanup temp file ─────────────────────────────────────────────────
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                tmp_dir = os.path.dirname(video_path)
                if os.path.isdir(tmp_dir) and not os.listdir(tmp_dir):
                    os.rmdir(tmp_dir)
            except OSError as e:
                logger.warning("Temp-file removal failed: %s", e)

        try:
            await status.delete()
        except Exception:
            pass

    if ok:
        log_download(user, url)
        await message.answer("✅ Готово! Чекаю наступне посилання 🎬")

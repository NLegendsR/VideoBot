import io
import logging
import os
import re

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, FSInputFile, Message

from config import ADMIN_ID, TELEGRAM_UPLOAD_LIMIT
from downloader import download_video, is_supported_url

logger = logging.getLogger(__name__)
router = Router()

URL_RE = re.compile(r"https?://\S+", re.I)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 <b>Привіт!</b> Надішли мені посилання на відео — я його скачаю.\n\n"
        "Підтримується: YouTube, TikTok, Instagram, Twitter/X, Facebook і ще тисячі сайтів.",
        parse_mode=ParseMode.HTML,
    )


@router.message()
async def on_message(message: Message, bot: Bot) -> None:
    user = message.from_user
    # В группах from_user может быть None только для анонимных админов —
    # обрабатываем и такой случай корректно
    user_id = user.id if user else None

    text = (message.text or message.caption or "").strip()
    is_admin = user_id == ADMIN_ID

    # ── 1. Extract URL ─────────────────────────────────────────────────────────
    url_match = URL_RE.search(text)
    if not url_match:
        # В группах молчим — не отвечаем на любой текст без ссылки
        if message.chat.type in ("group", "supergroup", "channel"):
            return
        await message.answer("🔗 Надішли посилання на відео!")
        return

    url = url_match.group(0)

    # ── 2. Check yt-dlp support (offline, fast) ────────────────────────────────
    if not is_supported_url(url):
        # В группах просто игнорируем неподдерживаемые ссылки
        if message.chat.type in ("group", "supergroup", "channel"):
            return
        # В личке сообщаем
        await message.answer(
            "⚠️ Ця платформа не підтримується.\n"
            "Спробуй посилання з YouTube, TikTok, Instagram, Twitter/X, Facebook тощо."
        )
        return

    quality_tag = " (🔝 максимальна якість)" if is_admin else ""
    status = await message.answer(
        f"⏳ <b>Завантажую…</b>{quality_tag}",
        parse_mode=ParseMode.HTML,
    )

    video_data = None
    ok = False

    try:
        # ── 3. Download ────────────────────────────────────────────────────────
        video_data, file_size = await download_video(url, is_admin=is_admin)
        size_mb = file_size / (1024 * 1024)

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

        # ── 4. Send video ──────────────────────────────────────────────────────
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")

        if isinstance(video_data, io.BytesIO):
            input_file = BufferedInputFile(video_data.read(), filename="video.mp4")
        else:
            input_file = FSInputFile(video_data)

        await message.answer_video(video=input_file)
        ok = True

    except ValueError as exc:
        await message.answer(f"❌ <b>Помилка:</b> {exc}", parse_mode=ParseMode.HTML)
    except RuntimeError:
        await message.answer("❌ Несподівана помилка. Спробуй ще раз.")
    finally:
        # Clean up disk file (only for admin path)
        if isinstance(video_data, str) and os.path.exists(video_data):
            try:
                os.remove(video_data)
                tmp_dir = os.path.dirname(video_data)
                if os.path.isdir(tmp_dir) and not os.listdir(tmp_dir):
                    os.rmdir(tmp_dir)
            except OSError as e:
                logger.warning("Temp-file removal failed: %s", e)

        try:
            await status.delete()
        except Exception:
            pass

    if ok:
        await message.answer("✅ Готово! 🎬")

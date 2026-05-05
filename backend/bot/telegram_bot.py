import asyncio
import logging
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

logger = logging.getLogger(__name__)

# Populated by main.py whenever a session is created
_session_registry: Dict[str, str] = {}  # session_id → drive_folder_id
_user_sessions: Dict[int, str] = {}     # telegram_user_id → session_id

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def register_session(session_id: str, drive_folder_id: str):
    _session_registry[session_id.upper()] = drive_folder_id


def build_dispatcher(drive_service) -> Dispatcher:
    """Return a configured Dispatcher. drive_service is passed via closure."""
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(
                "Отправьте /start с кодом сессии.\nПример: /start ABC12345"
            )
            return

        code = parts[1].strip().upper()
        if code not in _session_registry:
            await message.answer("❌ Сессия не найдена. Проверьте код.")
            return

        _user_sessions[message.from_user.id] = code
        await message.answer(
            f"✅ Подключено к сессии {code}.\n"
            "Отправляйте фото как файлы (скрепка → Файл), чтобы сохранить оригинальное качество."
        )

    @dp.message(F.document)
    async def handle_document(message: Message):
        user_id = message.from_user.id
        session_id = _user_sessions.get(user_id)
        if not session_id:
            await message.answer("Сначала укажите код сессии: /start КОД_СЕССИИ")
            return

        folder_id = _session_registry.get(session_id)
        if not folder_id:
            await message.answer("❌ Сессия не найдена.")
            return

        doc = message.document
        mime = doc.mime_type or "image/jpeg"
        if mime not in ALLOWED_MIMES:
            await message.answer("⚠️ Поддерживаются только фото (.jpg, .png, .webp, .heic)")
            return

        bot: Bot = message.bot
        file_info = await bot.get_file(doc.file_id)
        data = await bot.download_file(file_info.file_path)
        raw = data.read() if hasattr(data, "read") else bytes(data)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: drive_service.upload_file(
                doc.file_name or "photo.jpg", raw, mime, folder_id
            ),
        )
        await message.answer(f"✅ 1 фото добавлено в сессию {session_id}")

    return dp


async def run_bot(token: str, drive_service):
    bot = Bot(token=token)
    dp = build_dispatcher(drive_service)
    logger.info("Telegram bot polling started")
    await dp.start_polling(bot)

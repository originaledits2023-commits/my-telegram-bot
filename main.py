import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
import yt_dlp

# Bot tokeningizni shu yerga yozing yoki environment'dan oling
TOKEN = "SIZNING_BOT_TOKENINGIZ"

router = Router()
bot = Bot(token=TOKEN)
dp = Dispatcher()


# Foydalanuvchi holatlari (State)
class DownloadStates(StatesGroup):
  waiting_for_action = State()


# 1. Start komandasi
@router.message(CommandStart())
async def cmd_start(message: Message):
  await message.answer(
      "Salom! Menga Instagram, TikTok videosi linkini yoki musiqa"
      " nomini/linkini yuboring. Men sizga kerakli variantlarni"
      " taqdim etaman!"
  )


# 2. Link yoki matn kelganda ishlovchi qism
@router.message(F.text)
async def handle_user_input(message: Message, state: FSMContext):
  user_text = message.text.strip()

  # Link ekanligini yoki shunchaki matn ekanligini aniqlaymiz
  if (
      "instagram.com" in user_text
      or "tiktok.com" in user_text
      or "http" in user_text
  ):
    # Agar link bo'lsa, video uchun tugmalar chiqaramiz
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Videoni yuklab olish",
                    callback_data=f"dl_video:{user_text}",
                ),
                InlineKeyboardButton(
                    text="🎵 Faqat audiosini olish",
                    callback_data=f"dl_audio:{user_text}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="cancel"
                )
            ],
        ]
    )
    await message.answer(
        "Quyidagi variantlardan birini tanlang:", reply_markup=keyboard
    )

  else:
    # Agar musiqa nomi yuborilgan bo'lsa
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎧 Musiqani topish va yuklash",
                    callback_data=f"find_music:{user_text}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="cancel"
                )
            ],
        ]
    )
    await message.answer(
        f"'{user_text}' bo'yicha musiqa qidiraylikmi?", reply_markup=keyboard
    )


# 3. Tugmalar bosilgandagi amallar (Callback Query)
@router.callback_query(F.data.startswith("dl_video:"))
async def process_video_download(callback: CallbackQuery):
  url = callback.data.split(":", 1)[1]
  await callback.message.edit_text(
      "⏳ Video yuklab olinmoqda, biroz kuting..."
  )

  try:
    # yt-dlp yordamida videoni yuklab olish
    ydl_opts = {
        "format": "mp4",
        "outtmpl": "video.mp4",
        "max_filesize": 50 * 1024 * 1024,  # Telegram limiti uchun 50MB
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      ydl.download([url])

    # Videoni foydalanuvchiga yuborish
    from aiogram.types import FSInputFile

    video_file = FSInputFile("video.mp4")
    await callback.message.answer_video(video_file)
    await callback.message.delete()
  except Exception as e:
    await callback.message.edit_text(
        f"❌ Xatolik yuz berdi: Videoni yuklab bo'lmadi."
    )


@router.callback_query(F.data.startswith("dl_audio:"))
async def process_audio_download(callback: CallbackQuery):
  url = callback.data.split(":", 1)[1]
  await callback.message.edit_text("⏳ Audio formatga o'tkazilmoqda...")

  try:
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "outtmpl": "audio",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      ydl.download([url])

    from aiogram.types import FSInputFile

    audio_file = FSInputFile("audio.mp3")
    await callback.message.answer_audio(audio_file)
    await callback.message.delete()
  except Exception as e:
    await callback.message.edit_text(
        f"❌ Xatolik yuz berdi: Audioni yuklab bo'lmadi."
    )


@router.callback_query(F.data == "cancel")
async def cancel_process(callback: CallbackQuery):
  await callback.message.edit_text("Amaliyot bekor qilindi.")


async def main():
  dp.include_router(router)
  await bot.delete_webhook(drop_pending_updates=True)
  await dp.start_polling(bot)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  asyncio.run(main())

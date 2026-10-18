import asyncio
import json
import logging
import os
import re

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web
from google import genai
from google.genai import types as genai_types
import yt_dlp

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ai_client = None
if GEMINI_API_KEY:
  ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Guruh uchun Loki AI Prompti
LOKI_PROMPT = """
Sening isming Loki. Guruh chatida foydalanuvchilar bilan do'stona, samimiy va hazil-mutoyibali muloqot qil.
Javoblaring qisqa (1-2 cümlə) va samimiy bo'lsin.
"""

# Vaqtinchalik qidiruv natijalarini saqlash xotirasi
SEARCH_CACHE = {}


# --- /START BUYRUG'I ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
  text = (
      f"Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
      f"🎵 <b>Musiqa qidirish:</b> Qo'shiq nomi yoki ijrochini yozing;\n"
      f"📸 <b>Instagram / TikTok:</b> Reel, Post yoki Video havolasini"
      " yuboring;\n"
      f"👥 <b>Guruhda ishlash:</b> Botga reply qilib yozsangiz javob beraman."
  )
  await message.answer(text, parse_mode=ParseMode.HTML)


# --- GURUHDA AI JAVOBI (REPLY QILINGANDA) ---
@dp.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.reply_to_message
)
async def group_ai_reply(message: types.Message):
  if message.reply_to_message.from_user.id != bot.id or not ai_client:
    return

  await bot.send_chat_action(message.chat.id, action="typing")
  try:
    config = genai_types.GenerateContentConfig(
        system_instruction=LOKI_PROMPT,
        max_output_tokens=80,
        temperature=0.8,
    )
    prompt_text = (
        f"Guruhdagi xabar: {message.reply_to_message.text}\nJavob:"
        f" {message.text}"
    )

    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(
        None,
        lambda: ai_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt_text, config=config
        ),
    )

    if res.text:
      await message.reply(res.text.strip())
  except Exception as e:
    logging.error(f"AI error: {e}")


# --- MUSIQA QIDIRISH (1-8 TUGMALAR RO'YXATI) ---
async def search_music_results(query: str, message: types.Message):
  status_msg = await message.reply("🔍 Musiqalar qidirilmoqda...")

  ydl_opts = {
      "extract_flat": "in_playlist",
      "quiet": True,
      "default_search": "ytsearch8:",
  }

  try:
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = await loop.run_in_executor(
          None, lambda: ydl.extract_info(query, download=False)
      )

    entries = info.get("entries", [])
    if not entries:
      await status_msg.edit_text("❌ Hech qanday musiqa topilmadi.")
      return

    text = f"<b>{query}</b>\n\n"
    buttons = []
    row = []

    for idx, entry in enumerate(entries[:8], 1):
      title = entry.get("title", "Unknown")
      duration = entry.get("duration", 0)
      m, s = divmod(int(duration), 60) if duration else (0, 0)
      dur_str = f"{m}:{s:02d}" if duration else ""

      text += f"{idx}. <i>{title}</i> <b>{dur_str}</b>\n"

      vid_id = entry.get("id")
      SEARCH_CACHE[vid_id] = title
      row.append(
          InlineKeyboardButton(
              text=str(idx), callback_data=f"dlmusic_{vid_id}"
          )
      )

      if len(row) == 5 or idx == len(entries[:8]):
        buttons.append(row)
        row = []

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await status_msg.edit_text(
        text, parse_mode=ParseMode.HTML, reply_markup=markup
    )

  except Exception as e:
    logging.error(f"Search error: {e}")
    await status_msg.edit_text("❌ Musiqa qidirishda xatolik yuz berdi.")


# --- TUGMA BOSILGANDA MUSIQANI YUKLAB BERISH ---
@dp.callback_query(F.data.startswith("dlmusic_"))
async def download_selected_music(call: types.CallbackQuery):
  vid_id = call.data.split("_")[1]
  url = f"https://www.youtube.com/watch?v={vid_id}"

  await call.answer("📥 Musiqa yuklanmoqda...")
  status_msg = await call.message.answer("📥 Audio tayyorlanmoqda...")

  ydl_opts = {
      "format": "bestaudio/best",
      "outtmpl": "downloads/%(id)s.%(ext)s",
      "postprocessors": [{
          "key": "FFmpegExtractAudio",
          "preferredcodec": "mp3",
          "preferredquality": "192",
      }],
      "quiet": True,
  }

  try:
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = await loop.run_in_executor(
          None, lambda: ydl.extract_info(url, download=True)
      )
      filename = f"downloads/{vid_id}.mp3"
      title = info.get("title", "Music")

      audio_file = FSInputFile(filename)
      await call.message.answer_audio(
          audio_file, caption=f"🎵 <b>{title}</b>", parse_mode=ParseMode.HTML
      )

      if os.path.exists(filename):
        os.remove(filename)
      await status_msg.delete()

  except Exception as e:
    logging.error(f"DL music error: {e}")
    await status_msg.edit_text("❌ Musiqani yuklab bo'lmadi.")


# --- INSTAGRAM & TIKTOK VIDEO YUKLASH ---
async def download_social_video(url: str, message: types.Message):
  status_msg = await message.reply("🎬 Video yuklanmoqda...")

  ydl_opts = {
      "format": "bestvideo+bestaudio/best",
      "outtmpl": "downloads/%(id)s.%(ext)s",
      "merge_output_format": "mp4",
      "quiet": True,
  }

  try:
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = await loop.run_in_executor(
          None, lambda: ydl.extract_info(url, download=True)
      )
      filename = ydl.prepare_filename(info)
      if not filename.endswith(".mp4") and os.path.exists(
          filename.rsplit(".", 1)[0] + ".mp4"
      ):
        filename = filename.rsplit(".", 1)[0] + ".mp4"

      video_file = FSInputFile(filename)
      await message.answer_video(video_file, caption="✨ Video yuklandi!")

      if os.path.exists(filename):
        os.remove(filename)
      await status_msg.delete()

  except Exception as e:
    logging.error(f"Video error: {e}")
    await status_msg.edit_text("❌ Videoni yuklab bo'lmadi.")


# --- SHAXSIY CHAT XABARLARINI QABUL QILISH ---
@dp.message(F.chat.type == ChatType.PRIVATE, F.text)
async def handle_private_messages(message: types.Message):
  text = message.text.strip()
  if "instagram.com" in text or "tiktok.com" in text:
    await download_social_video(text, message)
  else:
    await search_music_results(text, message)


# --- RENDER PORT DUMMY SERVER ---
async def handle_ping(request):
  return web.Response(text="Bot runs smooth!")


async def main():
  if not os.path.exists("downloads"):
    os.makedirs("downloads")

  app = web.Application()
  app.router.add_get("/", handle_ping)
  runner = web.AppRunner(app)
  await runner.setup()
  port = int(os.environ.get("PORT", 10000))
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()

  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())

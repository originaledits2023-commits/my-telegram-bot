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
else:
  logging.warning("⚠️ GEMINI_API_KEY topilmadi! AI ishlamaydi.")

LOKI_PROMPT = """
Sening isming Loki (God of Stories). Guruh chatida muloqot qilayapsan.
Qoidalaring:
1. Samimiy, biroz pichingli va guruhdagi kayfiyatga (vibe) mos javob ber.
2. Maksimal 1-2 ta qisqa jumla yoz.
3. O'zbek tilida gapir.
"""


# --- /START BUYRUG'I ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
  text = (
      f"Assalomu alaykum, <b>{message.from_user.first_name}</b>!\n\n"
      f"🎵 <b>Musiqa qidirish:</b> Qo'shiq nomi yoki ijrochini yozing;\n"
      f"📸 <b>Instagram / TikTok:</b> Reel yoki Video havolasini yuboring;\n"
      f"👥 <b>Guruhda AI:</b> Bot admin bo'lsa va reply qilinsa, Loki javob"
      " beradi."
  )
  await message.answer(text, parse_mode=ParseMode.HTML)


# --- GURUHDA AI JAVOBI (REPLY QILINGANDA) ---
@dp.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.reply_to_message
)
async def group_ai_reply(message: types.Message):
  # Faqat botning o'ziga reply qilinganda
  if message.reply_to_message.from_user.id != bot.id:
    return

  if not ai_client:
    logging.info("AI client sozlanmagan, GEMINI_API_KEY yo'q.")
    return

  await bot.send_chat_action(message.chat.id, action="typing")
  try:
    config = genai_types.GenerateContentConfig(
        system_instruction=LOKI_PROMPT,
        max_output_tokens=70,
        temperature=0.8,
    )
    prompt_text = (
        f"Guruh xabari: {message.reply_to_message.text}\nFoydalanuvchi:"
        f" {message.text}"
    )

    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(
        None,
        lambda: ai_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt_text, config=config
        ),
    )

    if res and res.text:
      await message.reply(res.text.strip())
  except Exception as e:
    logging.error(f"Loki AI Error: {e}")


# --- MUSIQA QIDIRISH (1-8 VARIANTLAR) ---
@dp.message(F.chat.type == ChatType.PRIVATE, F.text)
async def handle_private_messages(message: types.Message):
  text = message.text.strip()

  if "instagram.com" in text or "tiktok.com" in text:
    await download_social_video(text, message)
    return

  # Musiqa qidiruv
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
          None, lambda: ydl.extract_info(text, download=False)
      )

    entries = info.get("entries", [])
    if not entries:
      await status_msg.edit_text("❌ Hech qanday musiqa topilmadi.")
      return

    msg_text = f"🎵 <b>{text}</b> bo'yicha natijalar:\n\n"
    buttons = []
    row = []

    for idx, entry in enumerate(entries[:8], 1):
      title = entry.get("title", "Unknown Title")
      duration = entry.get("duration", 0)
      m, s = divmod(int(duration), 60) if duration else (0, 0)
      dur_str = f"{m}:{s:02d}" if duration else ""

      msg_text += f"{idx}. <b>{title}</b> <i>({dur_str})</i>\n"

      vid_id = entry.get("id")
      row.append(
          InlineKeyboardButton(
              text=str(idx), callback_data=f"dlmusic_{vid_id}"
          )
      )

      if len(row) == 4 or idx == len(entries[:8]):
        buttons.append(row)
        row = []

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await status_msg.edit_text(
        msg_text, parse_mode=ParseMode.HTML, reply_markup=markup
    )

  except Exception as e:
    logging.error(f"Search error: {e}")
    await status_msg.edit_text("❌ Qo'shiq qidirishda xatolik yuz berdi.")


# --- TUGMA BOSILGANDA MUSIQANI YUKLAB YUBORISH ---
@dp.callback_query(F.data.startswith("dlmusic_"))
async def download_selected_music(call: types.CallbackQuery):
  vid_id = call.data.split("_")[1]
  url = f"https://www.youtube.com/watch?v={vid_id}"

  await call.answer("📥 Musiqa yuklanmoqda...")
  status_msg = await call.message.answer("📥 Audio yuklab olinmoqda...")

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
      title = info.get("title", "Musiqa")
      filename = f"downloads/{vid_id}.mp3"

      if not os.path.exists(filename):
        # Ba'zan kengaytma har xil bo'lib qolishi mumkinligini tekshiramiz
        for f in os.listdir("downloads"):
          if f.startswith(vid_id):
            filename = os.path.join("downloads", f)
            break

      audio_file = FSInputFile(filename)
      await call.message.answer_audio(
          audio_file, caption=f"🎵 <b>{title}</b>", parse_mode=ParseMode.HTML
      )

      if os.path.exists(filename):
        os.remove(filename)
      await status_msg.delete()

  except Exception as e:
    logging.error(f"DL music error: {e}")
    await status_msg.edit_text(
        "❌ Musiqani yuklab bo'lmadi. Boshqa raqamni tanlab ko'ring."
    )


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
      await message.answer_video(video_file, caption="✨ Video yuklab olindi!")

      if os.path.exists(filename):
        os.remove(filename)
      await status_msg.delete()

  except Exception as e:
    logging.error(f"Video error: {e}")
    await status_msg.edit_text("❌ Videoni yuklab bo'lmadi.")


# --- DUMMY SERVER (RENDER) ---
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

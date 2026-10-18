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
import yt_dlp

logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR VA ENVIRONMENT VARIABLE'LAR ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OWNER_ID = 8774778304  # O'zingizning Telegram ID'ingizni yozing

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Gemini AI Sozlamasi (Loki GOS xarakteri)
ai_client = None
if GEMINI_API_KEY:
  ai_client = genai.Client(api_key=GEMINI_API_KEY)

LOKI_SYSTEM_PROMPT = """
Sening isming Loki (God of Stories). Sening xaraktering:
- Juda aqlli, vazmin, o'ychan, bosiq va mag'rur.
- Hech qachon uzun va valdiragan javob bermaysan. Javoblaring qisqa, lirik va chuqur mantiqqa ega bo'lsin.
- O'zbek tilida gapirasan.
- Javoblaring maksimal 2-3 ta jumladan oshmasin.
"""

FAVORITES_FILE = "favorites.json"


def load_favorites():
  if not os.path.exists(FAVORITES_FILE):
    return {"videos": [], "songs": []}
  try:
    with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {"videos": [], "songs": []}


def save_favorites(data):
  with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)


# --- /START BUYRUG'I ---
@dp.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def start_command(message: types.Message):
  kb = [
      [
          InlineKeyboardButton(
              text="🎬 Saralangan Videolar", callback_data="fav_videos"
          ),
          InlineKeyboardButton(
              text="🎵 Saralangan Musiqalar", callback_data="fav_songs"
          ),
      ]
  ]
  if message.from_user.id == OWNER_ID:
    kb.append([
        InlineKeyboardButton(
            text="⚙️ Owner Dashboard", callback_data="owner_dashboard"
        )
    ])

  caption = (
      f"Salom <b>{message.from_user.full_name}</b>! ⚡\n\n"
      f"📜 <b>Bot imkoniyatlari:</b>\n"
      f"• <b>Instagram / TikTok linki</b> – Videoni sifatli yuklab beradi.\n"
      f"• <b>Musiqa nomi yoki ijrochi</b> – Qo'shiqni qidirib yuklab"
      " beradi.\n"
      f"• <b>Guruhlarda</b> – Bot admin bo'lsa va uning xabariga reply qilinsa,"
      " <b>Loki (God of Stories)</b> AI javob beradi."
  )
  await message.answer(
      caption,
      parse_mode=ParseMode.HTML,
      reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
  )


# --- OWNER DASHBOARD ---
@dp.callback_query(F.data == "owner_dashboard")
async def owner_dashboard_handle(callback: types.CallbackQuery):
  if callback.from_user.id != OWNER_ID:
    await callback.answer("Bu bo'lim faqat bot egasi uchun!", show_alert=True)
    return
  favs = load_favorites()
  text = (
      f"⚙️ <b>Owner Dashboard</b>\n\n"
      f"🎥 Videolar: {len(favs.get('videos', []))} ta\n"
      f"🎵 Musiqalar: {len(favs.get('songs', []))} ta\n\n"
      f"💡 <i>Yangi media qo'shish uchun botga Video yoki Audio yuboring.</i>"
  )
  await callback.message.edit_text(text, parse_mode=ParseMode.HTML)


# --- GURUHDA LOKI AI (FAQAT REPLY VA ADMIN BO'LGANDA) ---
@dp.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.reply_to_message
)
async def handle_group_loki_ai(message: types.Message):
  # Botga reply qilinganini va reply qilingan xabar botniki ekanini tekshirish
  if message.reply_to_message.from_user.id != bot.id:
    return

  # Bot guruhda Admin ekanligini tekshirish
  member = await bot.get_chat_member(message.chat.id, bot.id)
  if member.status not in ("administrator", "creator"):
    return

  if not ai_client:
    return

  try:
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{LOKI_SYSTEM_PROMPT}\nFoydalanuvchi: {message.text}\nLoki:",
    )
    if response.text:
      await message.reply(response.text.strip())
  except Exception as e:
    logging.error(f"Loki AI error: {e}")


# --- INSTAGRAM & TIKTOK VIDEO YUKLASH ---
async def download_media_video(url: str, message: types.Message):
  status_msg = await message.reply("🎬 Video yuklanmoqda...")

  ydl_opts = {
      "format": "bestvideo+bestaudio/best",
      "outtmpl": "downloads/%(id)s.%(ext)s",
      "quiet": True,
      "merge_output_format": "mp4",
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
      await message.answer_video(
          video_file, caption="✨ @downloadwithzerobot orqali yuklab olindi"
      )

      if os.path.exists(filename):
        os.remove(filename)
      await status_msg.delete()

  except Exception as e:
    logging.error(f"Video download error: {e}")
    await status_msg.edit_text(
        "❌ Videoni yuklab bo'lmadi. Havola to'g'riligini tekshiring."
    )


# --- MUSIQA QIDIRISH (YT-DLP) ---
async def download_music_by_query(query: str, message: types.Message):
  status_msg = await message.reply(f"🔍 <b>{query}</b> qidirilmoqda...")

  ydl_opts = {
      "format": "bestaudio/best",
      "outtmpl": "downloads/%(id)s.%(ext)s",
      "postprocessors": [{
          "key": "FFmpegExtractAudio",
          "preferredcodec": "mp3",
          "preferredquality": "192",
      }],
      "quiet": True,
      "default_search": "ytsearch1:",
  }

  try:
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = await loop.run_in_executor(
          None, lambda: ydl.extract_info(query, download=True)
      )
      if "entries" in info:
        info = info["entries"][0]

      filename = f"downloads/{info['id']}.mp3"
      title = info.get("title", query)
      performer = info.get("uploader", "Unknown Artist")

      audio_file = FSInputFile(filename)
      await message.answer_audio(
          audio, title=title, performer=performer, caption="🎵 Musiqa tayyor!"
      )

      if os.path.exists(filename):
        os.remove(filename)
      await status_msg.delete()

  except Exception as e:
    logging.error(f"Music download error: {e}")
    await status_msg.edit_text("❌ Musiqa topilmadi.")


# --- SHAXSIY CHATDA MATN VA LINKLARNI QABUL QILISH ---
@dp.message(F.chat.type == ChatType.PRIVATE, F.text)
async def handle_private_text(message: types.Message):
  text = message.text.strip()

  # Links (Instagram, TikTok)
  if "instagram.com" in text or "tiktok.com" in text:
    await download_media_video(text, message)
  else:
    # Qo'shiq qidiruvi
    await download_music_by_query(text, message)


# --- DUMMY WEB SERVER (RENDER 24/7 UYGO'Q TURISHI UCHUN) ---
async def handle_ping(request):
  return web.Response(text="Loki Bot is alive & watching!")


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

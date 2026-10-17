import asyncio
import json
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web
import yt_dlp

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 8774778304  # O'zingizning Telegram ID'ingizni yozing

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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


def get_main_menu(user_id):
  kb = [[
      InlineKeyboardButton(
          text="🎬 Saralangan Videolar", callback_data="fav_videos"
      ),
      InlineKeyboardButton(
          text="🎵 Saralangan Musiqalar", callback_data="fav_songs"
      ),
  ]]
  if user_id == OWNER_ID:
    kb.append([
        InlineKeyboardButton(
            text="⚙️ Owner Dashboard", callback_data="owner_dashboard"
        )
    ])
  return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(Command("start"))
async def start_command(message: types.Message):
  text = (
      f"Salom **{message.from_user.full_name}**!\n\n"
      f"🎵 **Qo'shiq nomi** yoki **ijrochini** yozing – musiqasini yuklab"
      " beraman!\n"
      f"🎬 Yoki Instagram/TikTok havolasini yuboring."
  )
  await message.answer(
      text,
      parse_mode=ParseMode.MARKDOWN,
      reply_markup=get_main_menu(message.from_user.id),
  )


# --- OWNER DASHBOARD ---
@dp.callback_query(F.data == "owner_dashboard")
async def owner_dashboard_handle(callback: types.CallbackQuery):
  if callback.from_user.id != OWNER_ID:
    await callback.answer("Bu bo'lim faqat bot egasi uchun!", show_alert=True)
    return
  favs = load_favorites()
  text = (
      f"⚙️ **Owner Dashboard**\n\n"
      f"🎥 Videolar: {len(favs.get('videos', []))} ta\n"
      f"🎵 Musiqalar: {len(favs.get('songs', []))} ta\n\n"
      f"💡 *Media saqlash uchun botga Video yoki Audio yuboring.*"
  )
  await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)


@dp.message(
    F.from_user.id == OWNER_ID,
    F.content_type.in_({"video", "audio", "document"}),
)
async def handle_owner_media_upload(message: types.Message):
  media_type = "video" if message.video else "song"
  file_id = (
      message.video.file_id
      if message.video
      else (
          message.audio.file_id
          if message.audio
          else message.document.file_id
      )
  )
  kb = InlineKeyboardMarkup(
      inline_keyboard=[[
          InlineKeyboardButton(
              text="➕ Bazaga qo'shish",
              callback_data=f"savefav_{media_type}_{file_id}",
          )
      ]]
  )
  await message.reply(
      "👑 **Owner:** Ushbu mediani bazangizga qo'shasizmi?",
      reply_markup=kb,
  )


@dp.callback_query(F.data.startswith("savefav_"))
async def save_to_favorites_callback(callback: types.CallbackQuery):
  if callback.from_user.id != OWNER_ID:
    return
  _, media_type, file_id = callback.data.split("_", 2)
  favs = load_favorites()
  category = "videos" if media_type == "video" else "songs"
  if file_id not in favs[category]:
    favs[category].append(file_id)
    save_favorites(favs)
    await callback.answer("✅ Saqlandi!", show_alert=True)
  else:
    await callback.answer("⚠️ Allaqachon bor!", show_alert=True)


@dp.callback_query(F.data.in_({"fav_videos", "fav_songs"}))
async def send_fav_media(callback: types.CallbackQuery):
  favs = load_favorites()
  category = "videos" if callback.data == "fav_videos" else "songs"
  items = favs.get(category, [])

  if not items:
    await callback.answer("Bazada ma'lumot yo'q 🤷‍♂️", show_alert=True)
    return

  await callback.answer("Yuklanmoqda...")
  for file_id in items:
    if category == "videos":
      await callback.message.answer_video(file_id)
    else:
      await callback.message.answer_audio(file_id)


# --- MUSIQA QIDIRISH VA YUKLASH (YT-DLP) ---
@dp.message(F.text)
async def handle_text_requests(message: types.Message):
  query = message.text.strip()
  status_msg = await message.reply(
      f"🔍 **{query}** bo'yicha musiqa qidirilmoqda...",
      parse_mode=ParseMode.MARKDOWN,
  )

  # yt-dlp yordamida audio qidirish va yuklab olish
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

      await status_msg.edit_text("📤 Musiqa yuborilmoqda...")

      audio_file = FSInputFile(filename)
      await message.answer_audio(audio_file, caption=f"🎵 **{title}**")

      # Yuklangan vaqtinchalik faylni o'chirish
      if os.path.exists(filename):
        os.remove(filename)
      await status_msg.delete()

  except Exception as e:
    logging.error(f"Download error: {e}")
    await status_msg.edit_text(
        "❌ Musiqani yuklashda xatolik yuz berdi. Boshqa nom bilan qayta harakat"
        " qiling."
    )


# --- RENDER PORT DUMMY SERVER ---
async def handle_ping(request):
  return web.Response(text="Bot is live!")


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

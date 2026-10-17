import asyncio
import json
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web
import yt_dlp

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Konfiguratsiya
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 8774778304  # Telegram ID-ingizni shu yerga yozing (masalan: 123456789)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

FAVORITES_FILE = "favorites.json"


# JSON fayl bilan ishlash funksiyalari (Dashboard ma'lumotlari)
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


# Klaviaturalar (Menyu)
def get_main_menu(user_id):
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
  # Faqat bot egasiga Dashboard tugmasi ko'rinadi
  if user_id == OWNER_ID:
    kb.append([
      InlineKeyboardButton(
        text="⚙️ Owner Dashboard", callback_data="owner_dashboard"
      )
    ])
  return InlineKeyboardMarkup(inline_keyboard=kb)


def get_music_options_keyboard(song_title):
  # Qo'shiq uchun turli versiyalar (Optionlar)
  kb = [
    [
      InlineKeyboardButton(
        text="🎧 Normal", callback_data=f"music_norm_{song_title[:20]}"
      ),
      InlineKeyboardButton(
        text="🐢 Slowed + Reverb", callback_data=f"music_slow_{song_title[:20]}"
      ),
    ],
    [
      InlineKeyboardButton(
        text="⚡ Sped Up", callback_data=f"music_fast_{song_title[:20]}"
      ),
      InlineKeyboardButton(
        text="📜 Qo'shiq Matni (Lyrics)",
        callback_data=f"lyrics_{song_title[:20]}",
      ),
    ],
  ]
  return InlineKeyboardMarkup(inline_keyboard=kb)


# /start Buyrug'i
@dp.message(Command("start"))
async def start_command(message: types.Message):
  user_name = message.from_user.full_name
  user_id = message.from_user.id

  text = (
    f"Salom **{user_name}**! Botga xush kelibsiz 🚀\n\n"
    f"📌 **Bot imkoniyatlari:**\n"
    f"1️⃣ Qo'shiq nomi yoki ijrochini yozing – turli versiyalarda (Slowed, Sped Up) va matni bilan topib beraman! 🎵\n"
    f"2️⃣ Instagram / TikTok havolasini yuboring – videoni yuklab beraman! 🎬\n"
    f"3️⃣ Bot egasining saralangan to'plamini ko'rish uchun pastdagi tugmalardan foydalaning."
  )
  await message.answer(
    text,
    parse_mode=ParseMode.MARKDOWN,
    reply_markup=get_main_menu(user_id),
  )


# --- OWNER DASHBOARD VA MEDIA QO'SHISH ---


@dp.callback_query(F.data == "owner_dashboard")
async def owner_dashboard_handle(callback: types.CallbackQuery):
  if callback.from_user.id != OWNER_ID:
    await callback.answer(
      "Bu bo'lim faqat bot egasi uchun!", show_alert=True
    )
    return

  favs = load_favorites()
  text = (
    f"⚙️ **Owner Dashboard**\n\n"
    f"📊 **Statistika:**\n"
    f"🎥 Bazadagi videolar: {len(favs.get('videos', []))} ta\n"
    f"🎵 Bazadagi musiqalar: {len(favs.get('songs', []))} ta\n\n"
    f"💡 *Yangi media qo'shish uchun botga shunchaki Video yoki Audio fayl yuboring!*"
  )
  await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)


# Owner Video yoki Musiqa yuborganda Dashboard'ga saqlash
@dp.message(
  F.from_user.id == OWNER_ID, F.content_type.in_({"video", "audio", "document"})
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
    "👑 **Owner:** Ushbu mediani bazangizga qo'shmoqchimisiz?",
    parse_mode=ParseMode.MARKDOWN,
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
    await callback.answer(
      "✅ Dashboard bazasiga saqlandi!", show_alert=True
    )
    await callback.message.edit_reply_markup(reply_markup=None)
  else:
    await callback.answer(
      "⚠️ Bu fayl allaqachon bazangizda bor!", show_alert=True
    )


# Saralangan videolarni ko'rish
@dp.callback_query(F.data.in_({"fav_videos", "fav_songs"}))
async def send_fav_media(callback: types.CallbackQuery):
  favs = load_favorites()
  category = "videos" if callback.data == "fav_videos" else "songs"
  items = favs.get(category, [])

  if not items:
    msg = "videolar" if category == "videos" else "musiqalar"
    await callback.answer(
      f"Hozircha bazada saralangan {msg} yo'q 🤷‍♂️", show_alert=True
    )
    return

  await callback.answer("Yuklanmoqda...")
  for file_id in items:
    if category == "videos":
      await callback.message.answer_video(file_id)
    else:
      await callback.message.answer_audio(file_id)


# --- MUSIQA QIDIRISH VA MATN/OPTIONLAR ---


@dp.message(F.text)
async def handle_text_requests(message: types.Message):

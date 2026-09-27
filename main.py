import os
import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import yt_dlp
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# ⚠️ O'ZINGIZNING TELEGRAM ID'INGIZNI BU YERGA YOZING!
OWNER_ID = 8774778304

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_urls = {}
DATA_FILE = "favorites.json"

# --- Ma'lumotlarni saqlash va yuklash ---
def load_favorites():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"videos": [], "songs": []}

def save_favorites(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

favorites = load_favorites()

# --- Render Web Server ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- /start buyrug'i ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_name = message.from_user.full_name
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Owner's Favorites", callback_data="show_favorites")
    builder.adjust(1)
    
    welcome_text = (
        f"**{user_name}**, yo, bro! 👋 Video & Music Downloader botga xush kelibsiz! 🚀\n\n"
        "1️⃣ **Instagram** yoki **TikTok** linkini yuboring — formatini tanlaysiz! 🎬/🎧\n"
        "2️⃣ **Musiqa nomini** yozing — qo'shiqni topib beraman! 🎶\n\n"
        "⭐ Bot egasining saralangan to'plamini ko'rish uchun pastdagi tugmani bosing!"
    )
    await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- ADMIN PANEL (/admin) ---
@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    user_name = message.from_user.full_name
    if message.from_user.id != OWNER_ID:
        await message.answer(f"**{user_name}**, siz bot egasi emassiz! 🛑", parse_mode="Markdown")
        return
    
    admin_text = (
        f"👑 **{user_name} (Owner Admin Panel)**\n\n"
        "Sevimlilar ro'yxatiga media qo'shish uchun:\n"
        "• **Video qo'shish:** Botga video yuborasiz va izohiga (caption) video nomini yozasiz.\n"
        "• **Musiqa qo'shish:** Botga audio/mp3 yuborasiz va izohiga musiqa nomini yozasiz.\n\n"
        "*(Bot o'zi avtomatik sevimlilar bazasiga saqlab oladi)*"
    )
    await message.answer(admin_text, parse_mode="Markdown")

# --- Owner tomonidan media saqlash ---
@dp.message(F.video & (F.from_user.id == OWNER_ID))
async def save_owner_video(message: types.Message):
    user_name = message.from_user.full_name
    title = message.caption or "Untitled Video"
    file_id = message.video.file_id
    
    favorites["videos"].append({"title": title, "file_id": file_id})
    save_favorites(favorites)
    await message.answer(f"✅ **{user_name}**, video sevimlilarga qo'shildi: **{title}**", parse_mode="Markdown")

@dp.message(F.audio & (F.from_user.id == OWNER_ID))
async def save_owner_song(message: types.Message):
    user_name = message.from_user.full_name
    title = message.caption or "Untitled Song"
    file_id = message.audio.file_id
    
    favorites["songs"].append({"title": title, "file_id": file_id})
    save_favorites(favorites)
    await message.answer(f"✅ **{user_name}**, musiqa sevimlilarga qo'shildi: **{title}**", parse_mode="Markdown")

# --- Favorites tugmasi bosilganda ---
@dp.callback_query(F.data == "show_favorites")
async def show_fav_menu(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Favorite Videos", callback_data="fav_videos")
    builder.button(text="🎧 Favorite Songs", callback_data="fav_songs")
    builder.adjust(2)
    
    await callback.message.answer(f"⭐ **{user_name}**, Owner's Favorite collection: Nima ko'rmoqchisiz?", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "fav_videos")
async def send_fav_videos(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    await callback.answer()
    if not favorites["videos"]:
        await callback.message.answer(f"**{user_name}**, hozircha sevimli videolar yo'q 🗿", parse_mode="Markdown")
        return
    
    await callback.message.answer(f"🔥 **{user_name}**, mana Owner's Favorite Videos:**", parse_mode="Markdown")
    for item in favorites["videos"]:
        await callback.message.answer_video(video=item["file_id"], caption=f"🎬 {item['title']}")

@dp.callback_query(F.data == "fav_songs")
async def send_fav_songs(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    await callback.answer()
    if not favorites["songs"]:
        await callback.message.answer(f"**{user_name}**, hozircha sevimli musiqalar yo'q 🎧", parse_mode="Markdown")
        return
    
    await callback.message.answer(f"🎵 **{user_name}**, mana Owner's Favorite Songs:**", parse_mode="Markdown")
    for item in favorites["songs"]:
        await callback.message.answer_audio(audio=item["file_id"], caption=f"🎧 {item['title']}")

# --- Oddiy yuklab olish va qidiruv mantig'i ---
@dp.message()
async def process_user_input(message: types.Message):
    user_name = message.from_user.full_name
    text = message.text.strip() if message.text else ""
    if not text:
        return

    # 1-HOLAT: Link yuborilganda
    if text.startswith("http://") or text.startswith("https://"):
        user_urls[message.from_user.id] = text
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🎬 Videoni yuklash", callback_data="dl_video")
        builder.button(text="🎧 Musiqasini yuklash", callback_data="dl_audio")
        builder.adjust(2)
        
        await message.answer(f"**{user_name}**, tanlang, bro: nimasini yuklab beray? 👇", reply_markup=builder.as_markup(), parse_mode="Markdown")

    # 2-HOLAT: Musiqa nomi yozilganda
    else:
        status_msg = await message.answer(f"**{user_name}**, qidiryapman: **{text}**... 🔍🎶", parse_mode="Markdown")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '/tmp/%(id)s.%(ext)s',
            'default_search': 'ytsearch1:',
            'quiet': True,
            'noplaylist': True,
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }
        
        try:
            loop = asyncio.get_event_loop()
            file_path = await loop.run_in_executor(None, lambda: _download(f"ytsearch1:{text}", ydl_opts))
            
            audio_file = types.FSInputFile(file_path)
            await message.answer_audio(audio=audio_file, caption=f"**{user_name}**, siz qidirgan trek: **{text}** 🎵⚡️", parse_mode="Markdown")
            
            if os.path.exists(file_path):
                os.remove(file_path)
            await status_msg.delete()
            
        except Exception as e:
            logging.error(f"Error searching music: {e}")
            await status_msg.edit_text(f"**{user_name}**, ayy, bunday musiqa topilmadi 💀", parse_mode="Markdown")

# --- TUGMALAR UCHUN HANDLERLAR ---
@dp.callback_query(F.data == "dl_video")
async def process_dl_video(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    user_id = callback.from_user.id
    url = user_urls.get(user_id)
    if not url:
        await callback.message.edit_text(f"**{user_name}**, ayy, havola eskiribdi. Linkni qayta yuboring 💀", parse_mode="Markdown")
        return

    await callback.answer()
    status_msg = await callback.message.edit_text(f"**{user_name}**, vibe'ni buzma, video yuklanyapti... ⏳🔥", parse_mode="Markdown")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, lambda: _download(url, ydl_opts))
        
        video_file = types.FSInputFile(file_path)
        await callback.message.answer_video(video=video_file, caption=f"**{user_name}**, mana, videongiz tayyor! 🗿⚡️", parse_mode="Markdown")
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error downloading video: {e}")
        await status_msg.edit_text(f"**{user_name}**, ayy, nimadir xato ketdi 💀 Video yopiq profildan yoki havola noto'g'ri.", parse_mode="Markdown")

@dp.callback_query(F.data == "dl_audio")
async def process_dl_audio(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    user_id = callback.from_user.id
    url = user_urls.get(user_id)
    if not url:
        await callback.message.edit_text(f"**{user_name}**, ayy, havola eskiribdi. Linkni qayta yuboring 💀", parse_mode="Markdown")
        return

    await callback.answer()
    status_msg = await callback.message.edit_text(f"**{user_name}**, videodan audio ajratib olinyapti... 🎧🔥", parse_mode="Markdown")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, lambda: _download(url, ydl_opts))
        
        audio_file = types.FSInputFile(file_path)
        await callback.message.answer_audio(audio=audio_file, caption=f"**{user_name}**, mana, audio tayyor! 🎧⚡️", parse_mode="Markdown")
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error extracting audio: {e}")
        await status_msg.edit_text(f"**{user_name}**, ayy, nimadir xato ketdi 💀 Audio ajratib bo'lmadi.", parse_mode="Markdown")

def _download(target, opts):
    clean_opts = {k: v for k, v in opts.items() if v is not None}
    with yt_dlp.YoutubeDL(clean_opts) as ydl:
        info = ydl.extract_info(target, download=True)
        if 'entries' in info:
            info = info['entries'][0]
        return ydl.prepare_filename(info)

async def main():
    await start_web_server()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

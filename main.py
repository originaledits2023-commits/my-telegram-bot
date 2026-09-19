import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
import yt_dlp
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchi havolalarini vaqtincha saqlash uchun lug'at (dict)
user_urls = {}

# Render portini aldash uchun veb-server
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

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "Yo, bro! 👋 Video & Music Downloader botga xush kelibsiz! 🚀\n\n"
        "1️⃣ **Instagram** yoki **TikTok** linkini yuboring — formatini tanlaysiz! 🎬/🎧\n"
        "2️⃣ **Musiqa nomini** yozing — qo'shiqni topib beraman! 🎶",
        parse_mode="Markdown"
    )

@dp.message()
async def process_user_input(message: types.Message):
    text = message.text.strip()
    
    # 1-HOLAT: Havola yuborilganda (Inline tugmalar chiqarish)
    if text.startswith("http://") or text.startswith("https://"):
        user_urls[message.from_user.id] = text
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🎬 Videoni yuklash", callback_data="dl_video")
        builder.button(text="🎧 Musiqasini yuklash", callback_data="dl_audio")
        builder.adjust(2)  # Tugmalarni bir qatorga qo'yadi
        
        await message.answer("Tanlang, bro: nimasini yuklab beray? 👇", reply_markup=builder.as_markup())

    # 2-HOLAT: Musiqa nomi yozilganda (Qidiruv)
    else:
        status_msg = await message.answer(f"Qidiryapman: **{text}**... 🔍🎶", parse_mode="Markdown")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '/tmp/%(id)s.%(ext)s',
            'default_search': 'ytsearch1:',
            'quiet': True,
            'noplaylist': True
        }
        
        try:
            loop = asyncio.get_event_loop()
            file_path = await loop.run_in_executor(None, lambda: _download(f"ytsearch1:{text}", ydl_opts))
            
            audio_file = types.FSInputFile(file_path)
            await message.answer_audio(audio=audio_file, caption=f"Siz qidirgan trek: **{text}** 🎵⚡️", parse_mode="Markdown")
            
            if os.path.exists(file_path):
                os.remove(file_path)
            await status_msg.delete()
            
        except Exception as e:
            logging.error(f"Error searching music: {e}")
            await status_msg.edit_text("Bla, bunday musiqa topilmadi 💀")

# --- TUGMALAR UCHUN HANDLERLAR ---

@dp.callback_query(F.data == "dl_video")
async def process_dl_video(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    url = user_urls.get(user_id)
    
    if not url:
        await callback.message.edit_text("Watta, havola eskiribdi. Iltimos, linkni qayta yuboring 💀")
        return

    await callback.answer()
    status_msg = await callback.message.edit_text("Biroz kuting, video yuklanyapti... ⏳🔥")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, lambda: _download(url, ydl_opts))
        
        video_file = types.FSInputFile(file_path)
        await callback.message.answer_video(video=video_file, caption="Mana, videongiz tayyor! 🗿⚡️")
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error downloading video: {e}")
        await status_msg.edit_text("Ayy, nimadir xato ketdi 💀 Video yopiq profildan yoki havola noto'g'ri.")

@dp.callback_query(F.data == "dl_audio")
async def process_dl_audio(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    url = user_urls.get(user_id)
    
    if not url:
        await callback.message.edit_text("Ayy, havola eskiribdi. Iltimos, linkni qayta yuboring 💀")
        return

    await callback.answer()
    status_msg = await callback.message.edit_text("Videodan audio ajratib olinyapti... 🎧🔥")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, lambda: _download(url, ydl_opts))
        
        audio_file = types.FSInputFile(file_path)
        await callback.message.answer_audio(audio=audio_file, caption="Mana, audio tayyor! 🎧⚡️")
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error extracting audio: {e}")
        await status_msg.edit_text("Ayy, nimadir xato ketdi 💀 Audio ajratib bo'lmadi.")

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

import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import yt_dlp
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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
    await message.answer("Yov bro! 👋 Reels, TikTok yoki YouTube linkini tashla, tayyorlab beraman 🚀")

@dp.message()
async def download_video(message: types.Message):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("Bro, bu link emas-ku 💀 To'g'ri link tashla!")
        return

    status_msg = await message.answer("SABR QIL, video yuklanyapti... ⏳🔥")

    # YouTube va Instagram uchun universal yt-dlp sozlamasi
ydl_opts = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    # YouTube bloki va bot tekshiruvini aylanib o'tish uchun:
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios']  # Brauzer emas, android/ios mijozi sifatida so'rov yuboradi
        }
    },
    'nocheckcertificate': True,
    'quiet': True
}

    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, lambda: _download(url, ydl_opts))

        video_file = types.FSInputFile(file_path)
        await message.answer_video(video=video_file, caption="Mana, tayyor! 🗿⚡️")
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text("Ayy, nimadir xato ketdi 💀 Video yopiq profildan yoki havola noto'g'ri.")

def _download(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def main():
    await start_web_server()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

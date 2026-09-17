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

# --- Render portini aldash uchun mini veb-server ---
async def handle(request):
    return web.Response(text="Bot is running live!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")
# ---------------------------------------------------

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Yov bro! 👋 Reels, TikTok yoki Shorts linkini jo'nat, tayyorlab beraman 🚀")

@dp.message()
async def download_video(message: types.Message):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("Bro, bu link emas-ku 💀 To'g'ri link tashla!")
        return

    status_msg = await message.answer("BIROZ KUT, video yuklanyapti... ⏳🔥")

ydl_opts = {
        # Formatni soddalashtiramiz (YouTube audio/video birlashtirishda xato bermasligi uchun)
        'format': 'best[ext=mp4]/best',
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        # YouTube blokirovkalarini aylanib o'tish uchun browser signaturasini qo'shamiz
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, lambda: _download(url, ydl_opts))

        video_file = types.FSInputFile(file_path)
        await message.answer_video(video=video_file, caption="Mana, tayyor! YANA KUTIB QOLAMAN 🗿⚡️")
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text("Ayy, nimadir xato ketdi 💀 Video yopiq profildan yoki link noto'g'ri!")

def _download(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def main():
    # Veb serverni ham, botni ham bir vaqtda yurgizamiz
    await start_web_server()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

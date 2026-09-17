import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

# Loggingni sozlash
logging.basicConfig(level=logging.INFO)

# Tokenni Render muhitidan olish
BOT_TOKEN = os.environ.get('8872678681:AAEf-_pWphwMCLLc8_4EL-V8Lgj5BgbJysA')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Salom! Bot Render serverida muvaffaqiyatli ishlayapti.")

@dp.message()
async def echo_cmd(message: types.Message):
    await message.answer(f"Siz yubordingiz: {message.text}")

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

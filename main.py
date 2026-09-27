import asyncio
import json
import logging
import os
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import google.generativeai as genai

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Konfiguratsiya va Muhit o'zgaruvchilari
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OWNER_ID = 8774778304  # Telegram ID ingizni shu yerga yozing

# Gemini AI Sozlash
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-3.8-flash')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

FAVORITES_FILE = "favorites.json"


# JSON fayl bilan ishlash funksiyalari
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


# Inline Klaviaturalar
def get_main_menu():
    kb = [
        [
            InlineKeyboardButton(
                text="🔥 Owner's Favorites", callback_data="owner_favs"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_favs_menu():
    kb = [
        [
            InlineKeyboardButton(
                text="🎬 Favorite Videos", callback_data="fav_videos"
            ),
            InlineKeyboardButton(
                text="🎵 Favorite Songs", callback_data="fav_songs"
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# /start Buyrug'i
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_name = message.from_user.full_name
    text = (
        f"**{user_name}**, salom! Botga xush kelibsiz 🚀\n\n"
        f"1️⃣ Instagram / TikTok linkini yuboring – yuklab beraman! 🎬\n"
        f"2️⃣ Musiqa nomini yozing – topib beraman! 🎵\n"
        f"3️⃣ Guruhda botni admin qilib, ung Reply yoki Mention qilsangiz – AI javob beradi! 🤖\n\n"
        f"⭐ Bot egasining saralangan to'plamini ko'rish uchun pastdagi tugmani bosing!"
    )
    await message.answer(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu()
    )


# Owner uchun Media kelganda Sevimlilarga qo'shish tugmasi
@dp.message(
    F.from_user.id == OWNER_ID, F.content_type.in_({"video", "audio", "document"})
)
async def handle_owner_media(message: types.Message):
    user_name = message.from_user.full_name
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
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Sevimlilarga qo'shish",
                    callback_data=f"addfav_{media_type}_{file_id}",
                )
            ]
        ]
    )
    await message.reply(
        f"**{user_name}**, ushbu mediani Sevimlilar to'plamiga qo'shasizmi?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )


# Callback Handlerlar (Tugmalar uchun)
@dp.callback_query(F.data == "owner_favs")
async def show_fav_categories(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    await callback.message.edit_text(
        f"**{user_name}**, Owner's Favorite collection: Nima ko'rmoqchisiz?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_favs_menu(),
    )


@dp.callback_query(F.data.in_({"fav_videos", "fav_songs"}))
async def send_fav_list(callback: types.CallbackQuery):
    user_name = callback.from_user.full_name
    favs = load_favorites()
    category = "videos" if callback.data == "fav_videos" else "songs"
    items = favs.get(category, [])

    if not items:
        msg = "videolar" if category == "videos" else "musiqalar"
        await callback.answer(
            f"{user_name}, hozircha sevimli {msg} yo'q 🤷‍♂️", show_alert=True
        )
        return

    for file_id in items:
        if category == "videos":
            await callback.message.answer_video(file_id)
        else:
            await callback.message.answer_audio(file_id)


@dp.callback_query(F.data.startswith("addfav_"))
async def add_to_favorites(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return

    _, media_type, file_id = callback.data.split("_", 2)
    favs = load_favorites()
    category = "videos" if media_type == "video" else "songs"

    if file_id not in favs[category]:
        favs[category].append(file_id)
        save_favorites(favs)
        await callback.answer("✅ Sevimlilarga saqlandi!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
    else:
        await callback.answer("⚠️ Bu fayl allaqachon mavjud!", show_alert=True)


# Asosiy Matnli Xabarlarni Qayta Ishlash (AI & Musiqa)
@dp.message(F.text)
async def handle_text_messages(message: types.Message, bot: Bot):
    user_name = message.from_user.full_name
    text = message.text.strip()
    chat_type = message.chat.type

    # 1. Instagram / TikTok link bo'lsa (Barcha chatlarda ishlaydi)
    if "instagram.com" in text or "tiktok.com" in text:
        status_msg = await message.reply(
            f"**{user_name}**, media yuklanmoqda... ⏳",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Bu yerga yt-dlp orqali yuklash kodingizni qo'shasiz
        await status_msg.edit_text(
            f"**{user_name}**, media muvaffaqiyatli yuklandi! 🎬"
        )
        return

    # 2. Shaxsiy Chat (DM) bo'lsa
    if chat_type == ChatType.PRIVATE:
        # Shaxsiy chatda faqat musiqa qidirish xizmati ishlaydi
        status_msg = await message.reply(
            f"**{user_name}**, musiqa qidirilmoqda... 🎵",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Bu yerga SoundCloud (scsearch1:) orqali musiqa qidiruv kodingiz joylashadi
        return

    # 3. Guruhlar (Group / Supergroup)
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:

        # Bot guruhda admin ekanligini tekshirish
        bot_member = await bot.get_chat_member(message.chat.id, bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            return  # Admin bo'lmasa ishlamaydi

        # Reply yoki Mention qilinganini tekshirish
        bot_info = await bot.get_me()
        is_reply_to_bot = (
            message.reply_to_message
            and message.reply_to_message.from_user.id == bot_info.id
        )
        is_mentioned = (
            message.text and f"@{bot_info.username}" in message.text
        )

        if not (is_reply_to_bot or is_mentioned):
            return  # Mention yoki Reply bo'lmasa, umuman javob bermaydi

        clean_text = text.replace(f"@{bot_info.username}", "").strip()

        # Musiqa so'rovi bo'lsa
        if clean_text.lower().startswith(
            ("musiqa", "qo'shiq", "music", "top", "find")
        ):
            await message.reply(
                f"**{user_name}**, guruh uchun musiqa qidirilmoqda... 🎵",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Aks holda AI (Gemini 2.0 Flash) ishga tushadi
        status_msg = await message.reply(
            f"**{user_name}**, o'ylayapman... 🤖💭", parse_mode=ParseMode.MARKDOWN
        )
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: ai_model.generate_content(
                    f"Foydalanuvchi ismi: {user_name}. Unga o'zbek tilida Gen-Z uslubida, o'tkir va qiziqarli javob ber. So'rov: {clean_text}"
                ),
            )
            await status_msg.edit_text(
                f"**{user_name}**, {response.text}", parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"AI Error: {e}")
            await status_msg.edit_text(
                f"**{user_name}**, uzr, AI hozir javob bera olmadi 💀",
                parse_mode=ParseMode.MARKDOWN,
            )


import os
from aiohttp import web

# Render port talab qilgani uchun kichik veb-server
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    # Render botni 15 daqiqada o'chirib qo'ymasligi uchun port ochish
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


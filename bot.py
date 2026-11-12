import asyncio
import logging
import os
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

# ====== SOZLAMALAR ======
BOT_TOKEN = "8573705403:AAF6pRQkOqpxQbVjlUX2TvmwOGaZEqCFgww"
ADMIN_IDS = {8741693003}             # o'zingizning Telegram ID'ingiz (@userinfobot dan oling)
STORAGE_CHANNEL_ID = -1003296041901 # kinolar saqlanadigan kanal ID'si (bot shu kanalda admin bo'lishi kerak)
REQUIRED_CHANNEL = ""                # majburiy obuna uchun, masalan "@kanal_nomi". Kerak bo'lmasa bo'sh qoldiring
PROTECT_CONTENT = False              # True bo'lsa, kinoni yuklab olish/forward qilish taqiqlanadi
# ========================

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect("movies.db")
db.execute(
    "CREATE TABLE IF NOT EXISTS movies ("
    "code INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER NOT NULL, title TEXT)"
)
db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
db.commit()


def is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


async def is_subscribed(user_id: int) -> bool:
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


@dp.message(CommandStart())
async def start(message: Message):
    db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    db.commit()
    await message.answer("Salom! 🎬 Kino kodini yuboring, men kinoni topib beraman.")


# ---------- ADMIN ----------
@dp.message(F.video | F.document, F.from_user.id.in_(ADMIN_IDS))
async def add_movie(message: Message):
    """Admin video yuborsa, kanalga nusxalanadi va kod beriladi."""
    sent = await bot.copy_message(
        chat_id=STORAGE_CHANNEL_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    title = message.caption or ""
    cur = db.execute(
        "INSERT INTO movies (message_id, title) VALUES (?, ?)", (sent.message_id, title)
    )
    db.commit()
    await message.answer(f"✅ Kino qo'shildi. Kodi: <b>{cur.lastrowid}</b>", parse_mode="HTML")


@dp.message(Command("delete"))
async def delete_movie(message: Message):
    if not is_admin(message):
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.answer("Foydalanish: /delete 125")
    db.execute("DELETE FROM movies WHERE code = ?", (int(parts[1]),))
    db.commit()
    await message.answer("🗑 O'chirildi.")


@dp.message(Command("stats"))
async def stats(message: Message):
    if not is_admin(message):
        return
    users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    movies = db.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    await message.answer(f"👥 Foydalanuvchilar: {users}\n🎬 Kinolar: {movies}")


@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    """Yuboriladigan xabarga reply qilib /broadcast yozing."""
    if not is_admin(message):
        return
    if not message.reply_to_message:
        return await message.answer("Xabarga reply qilib /broadcast yozing.")
    ok = fail = 0
    for (uid,) in db.execute("SELECT user_id FROM users").fetchall():
        try:
            await bot.copy_message(uid, message.chat.id, message.reply_to_message.message_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # Telegram limitiga tushmaslik uchun
    await message.answer(f"Yuborildi: {ok}, xato: {fail}")


# ---------- FOYDALANUVCHI ----------
@dp.message(F.text.regexp(r"^\d+$"))
async def get_movie(message: Message):
    db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    db.commit()

    if not await is_subscribed(message.from_user.id):
        return await message.answer(
            f"Avval {REQUIRED_CHANNEL} kanaliga obuna bo'ling, so'ng kodni qayta yuboring."
        )

    row = db.execute(
        "SELECT message_id FROM movies WHERE code = ?", (int(message.text),)
    ).fetchone()
    if not row:
        return await message.answer("❌ Bunday kodli kino topilmadi.")

    await bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=STORAGE_CHANNEL_ID,
        message_id=row[0],
        protect_content=PROTECT_CONTENT,
    )


@dp.message()
async def fallback(message: Message):
    await message.answer("Kino kodini raqam ko'rinishida yuboring, masalan: 125")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


# ----------------------------------------
# НАСТРОЙКИ
# ----------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8468065089

PHOTO_FILE_ID = "AgACAgUAAxkBAAEcSFFpvKqbYr0IfiMOKypItDtDip7SXgACJw5rG8Vq6VX8OCc0sIop2AEAAwIAA3gAAzoE"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ----------------------------------------
# БАЗА ДАННЫХ (SQLite)
# ----------------------------------------

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    approved INTEGER DEFAULT 0
)
""")

conn.commit()


def approve_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, approved) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET approved=1 WHERE user_id=?", (user_id,))
    conn.commit()


def is_approved(user_id: int) -> bool:
    cursor.execute("SELECT approved FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1


# ----------------------------------------
# FSM
# ----------------------------------------

class Form(StatesGroup):
    about = State()
    source = State()


# ----------------------------------------
# МЕНЮ
# ----------------------------------------

def main_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏝 Создать ссылку", callback_data="create_link")],
            [InlineKeyboardButton(text="🤍 Мои объявления", callback_data="my_posts")],
            [InlineKeyboardButton(text="🐷 Вбив-состав", callback_data="vbiv_team")],
            [InlineKeyboardButton(text="🫧 Касса", callback_data="kassa")],
            [InlineKeyboardButton(text="🍬 Настройки", callback_data="settings")]
        ]
    )


async def send_main_menu(user_id, username):
    text = (
        f"🌿 Приветствуем тебя, {username}!\n\n"
        f"💎 Твой статус: Воркер\n"
        f"👨‍💻 Кол-во юзеров: 36\n"
        f"✨ Профитов: 0\n\n"
        f"❄️ Статус проекта: ✅ work\n\n"
        f"Куда дальше? 👇"
    )

    await bot.send_photo(
        chat_id=user_id,
        photo=PHOTO_FILE_ID,
        caption=text,
        reply_markup=main_menu_kb()
    )


# ----------------------------------------
# СТАРТ
# ----------------------------------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if is_approved(user_id):
        await send_main_menu(user_id, message.from_user.full_name)
        return

    await message.answer(
        f"🌿 Привет, {message.from_user.first_name}!\n\n"
        f"🆔 Твой ID: {user_id}\n\n"
        f"✨ Расскажи о себе:"
    )

    await state.set_state(Form.about)


@dp.message(Form.about)
async def about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await message.answer("Откуда узнал о проекте?")
    await state.set_state(Form.source)


@dp.message(Form.source)
async def source(message: Message, state: FSMContext):
    data = await state.get_data()

    user = message.from_user

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")
            ]
        ]
    )

    text = (
        f"📥 Новая заявка\n\n"
        f"👤 @{user.username}\n"
        f"🆔 {user.id}\n\n"
        f"📌 {data['about']}\n\n"
        f"🔗 {message.text}"
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)
    await message.answer("⏳ Ожидайте решения")

    await state.clear()


# ----------------------------------------
# ОДОБРЕНИЕ
# ----------------------------------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    await callback.answer()  # ✅ фикс загрузки

    try:
        user_id = int(callback.data.split("_")[1])

        approve_user(user_id)

        await send_main_menu(
            user_id,
            (await bot.get_chat(user_id)).full_name
        )

        await callback.message.edit_text("Заявка принята ✅")

    except Exception as e:
        print("ERROR:", e)


# ----------------------------------------
# ОТКЛОНЕНИЕ
# ----------------------------------------

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    await callback.answer()  # ✅ тоже обязательно

    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Ваша заявка отклонена")
    await callback.message.edit_text("Заявка отклонена ❌")


# ----------------------------------------
# КОМАНДЫ
# ----------------------------------------

@dp.message(F.text == "/menu")
async def menu(message: Message):
    if not is_approved(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        return

    await send_main_menu(message.from_user.id, message.from_user.full_name)


@dp.message(F.text == "/myid")
async def myid(message: Message):
    await message.answer(f"🆔 {message.from_user.id}")


# ----------------------------------------
# RUN
# ----------------------------------------

async def main():
    print("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

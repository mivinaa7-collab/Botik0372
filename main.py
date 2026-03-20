import asyncio
import os
import sqlite3
import uuid
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8468065089

PHOTO_FILE_ID = "AgACAgUAAxkBAAEcSFFpvKqbYr0IfiMOKypItDtDip7SXgACJw5rG8Vq6VX8OCc0sIop2AEAAwIAA3gAAzoE"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -------------------- БД --------------------

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    approved INTEGER DEFAULT 0,
    role TEXT DEFAULT 'worker',
    banned INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    project TEXT,
    price INTEGER,
    link TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER PRIMARY KEY,
    tag TEXT DEFAULT '#',
    domain TEXT DEFAULT 'Общий',
    payment TEXT DEFAULT 'TRC20',
    traffic INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    user_id INTEGER,
    time TEXT
)
""")

conn.commit()

# -------------------- УТИЛИТЫ --------------------

def log(action, user_id):
    cursor.execute(
        "INSERT INTO logs (action, user_id, time) VALUES (?, ?, ?)",
        (action, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

def get_role(user_id):
    cursor.execute("SELECT role FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "worker"

def set_role(user_id, role):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
    conn.commit()

def is_banned(user_id):
    cursor.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] == 1

def set_ban(user_id, value):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET banned=? WHERE user_id=?", (value, user_id))
    conn.commit()

set_role(ADMIN_ID, "admin")

def approve_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, approved) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET approved=1 WHERE user_id=?", (user_id,))
    conn.commit()

def is_approved(user_id):
    cursor.execute("SELECT approved FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

# -------------------- FSM --------------------

class Form(StatesGroup):
    about = State()
    source = State()
    price = State()

# -------------------- КНОПКИ --------------------

def main_menu_kb(user_id):
    buttons = [
        [InlineKeyboardButton(text="🏝 Создать ссылку", callback_data="create_link")],
        [InlineKeyboardButton(text="🤍 Мои объявления", callback_data="my_posts")],
        [InlineKeyboardButton(text="🍬 Настройки", callback_data="settings")]
    ]

    if get_role(user_id) == "admin":
        buttons.append([InlineKeyboardButton(text="🛠 Админ панель", callback_data="admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def projects_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇦 Приват", callback_data="proj_privat"),
         InlineKeyboardButton(text="🇺🇦 Ощад", callback_data="proj_oshad")],
        [InlineKeyboardButton(text="🇺🇦 Райффайзен", callback_data="proj_raif"),
         InlineKeyboardButton(text="🇺🇦 Дия", callback_data="proj_diya")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])

def generate_link(user_id, project):
    return f"https://example.com/{project}?user={user_id}&id={str(uuid.uuid4())[:8]}"

# -------------------- МЕНЮ --------------------

async def send_main_menu(user_id, username):
    await bot.send_photo(
        chat_id=user_id,
        photo=PHOTO_FILE_ID,
        caption=f"Привет {username}",
        reply_markup=main_menu_kb(user_id)
    )

# -------------------- СОЗДАНИЕ ССЫЛКИ --------------------

@dp.callback_query(F.data == "create_link")
async def create_link(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_caption("Выбери проект:", reply_markup=projects_kb())

@dp.callback_query(F.data.startswith("proj_"))
async def select_project(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    project = callback.data.split("_")[1]
    await state.update_data(project=project)

    await callback.message.edit_caption(f"Введи цену для {project}:")
    await state.set_state(Form.price)

@dp.message(Form.price)
async def get_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введи число")
        return

    data = await state.get_data()
    project = data["project"]
    price = int(message.text)
    user_id = message.from_user.id

    link = generate_link(user_id, project)

    cursor.execute(
        "INSERT INTO links (user_id, project, price, link) VALUES (?, ?, ?, ?)",
        (user_id, project, price, link)
    )
    conn.commit()

    await message.answer(f"Ссылка:\n{link}\nЦена: {price}")
    await state.clear()

# -------------------- МОИ ОБЪЯВЛЕНИЯ --------------------

@dp.callback_query(F.data == "my_posts")
async def my_posts(callback: CallbackQuery):
    await callback.answer()

    cursor.execute("SELECT project, price FROM links WHERE user_id=?", (callback.from_user.id,))
    rows = cursor.fetchall()

    text = "📭 Нет объявлений" if not rows else "\n".join(
        [f"{p} - {price} UAH" for p, price in rows]
    )

    await callback.message.edit_caption(text)

# -------------------- СТАРТ --------------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    if is_banned(message.from_user.id):
        await message.answer("🚫 Бан")
        return

    if is_approved(message.from_user.id):
        await send_main_menu(message.from_user.id, message.from_user.full_name)
        return

    await message.answer("Расскажи о себе:")
    await state.set_state(Form.about)

@dp.message(Form.about)
async def about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)
    await message.answer("Откуда узнал?")
    await state.set_state(Form.source)

@dp.message(Form.source)
async def source(message: Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data=f"approve_{user.id}"),
         InlineKeyboardButton(text="❌", callback_data=f"reject_{user.id}")]
    ])

    await bot.send_message(ADMIN_ID, f"{data['about']}\n{message.text}", reply_markup=kb)
    await message.answer("Жди")
    await state.clear()

# -------------------- АДМИН --------------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    await callback.answer()
    uid = int(callback.data.split("_")[1])
    approve_user(uid)
    await bot.send_message(uid, "Принят")
    await callback.message.edit_text("OK")

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    await callback.answer()
    uid = int(callback.data.split("_")[1])
    await bot.send_message(uid, "Отказ")
    await callback.message.edit_text("NO")

# -------------------- RUN --------------------

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

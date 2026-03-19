import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 8468065089  # ← вставь свой ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class Form(StatesGroup):
    about = State()
    source = State()


approved_users = set()


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id in approved_users:
        await message.answer("Ты уже одобрен ✅")
        return

    await message.answer(
        f"🌿 Привет, {message.from_user.first_name}!\n\n"
        f"🆔 Твой ID: {user_id}\n\n"
        f"✨ Расскажи немного о себе: в каких проектах работал, на какую роль хочешь попасть?"
    )

    await state.set_state(Form.about)


@dp.message(Form.about)
async def about(message: Message, state: FSMContext):
    await state.update_data(about=message.text)

    await message.answer(
        "✨ Хорошо, теперь введи тег или ссылку на канал, откуда узнал о проекте."
    )

    await state.set_state(Form.source)


@dp.message(Form.source)
async def source(message: Message, state: FSMContext):
    data = await state.get_data()

    about = data["about"]
    source = message.text
    user = message.from_user

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")
        ]
    ])

    text = (
        f"📥 Новая заявка\n\n"
        f"👤 @{user.username}\n"
        f"🆔 {user.id}\n\n"
        f"📌 О себе:\n{about}\n\n"
        f"🔗 Источник:\n{source}"
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)

    await message.answer("⏳ Спасибо! Ожидайте, пока администратор рассмотрит вашу заявку.")

    await state.clear()


@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    approved_users.add(user_id)

    await bot.send_message(
        user_id,
        "👻 Поздравляем! Ваша заявка принята.\n\n"
        "Подпишись на канал @your_channel\n\n"
        "После этого нажми /start"
    )

    await callback.message.edit_text("Заявка принята ✅")


@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Ваша заявка отклонена")

    await callback.message.edit_text("Заявка отклонена ❌")


@dp.message()
async def check(message: Message):
    if message.from_user.id not in approved_users:
        await message.answer("⛔ Сначала подай заявку через /start")
        return

    await message.answer("Ты внутри системы 😎")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

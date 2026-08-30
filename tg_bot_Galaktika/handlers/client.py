from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from database import get_or_create_user, get_user_transactions

router = Router()

def get_client_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Мой баланс"), KeyboardButton(text="📜 История баллов")],
            [KeyboardButton(text="🆔 Мой ID"), KeyboardButton(text="ℹ️ О баллах")]
        ],
        resize_keyboard=True
    )

def get_welcome_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏛 О нас", callback_data="about_lounge")]
        ]
    )

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await get_or_create_user(user.id, user.username or "", user.full_name or "")
    
    welcome_text = (
        f"👋 Здравствуйте, <b>{user.full_name}</b>!\n\n"
        f"Добро пожаловать в нашу бонусную программу лояльности! 🍸☕️\n\n"
        f"За каждую покупку в нашем заведении вам начисляются баллы, которые вы можете тратить на будущие заказы.\n\n"
        f"Используйте кнопки ниже для управления вашим балансом:"
    )
    await message.answer(welcome_text, reply_markup=get_client_keyboard(), parse_mode="HTML")
    
    # Отправляем инлайн-кнопку "О нас" отдельным сообщением или прикрепляем к приветствию
    about_prompt = "Узнайте больше о нашем заведении 👇"
    await message.answer(about_prompt, reply_markup=get_welcome_inline_keyboard())

@router.callback_query(F.data == "about_lounge")
async def cb_about_lounge(callback: CallbackQuery):
    await callback.answer()
    about_text = (
        f"🌟 <b>Лаунж-бар Galaktika в Жуковском</b> 🌟\n\n"
        f"Добро пожаловать в наше уютное пространство атмосферного отдыха! 🍸💨\n\n"
        f"✨ К вашим услугам:\n"
        f"• Премиальные паровые коктейли (кальяны) с большим выбором табаков\n"
        f"• Авторский чай, элитный кофе, освежающие лимонады и крафтовые напитки\n"
        f"• Уютная атмосфера, стильный интерьер и приятная музыка для отдыха с друзьями или второй половинкой\n"
        f"• PlayStation, настольные игры и трансляции матчей\n\n"
        f"📍 <b>Адрес:</b> г. Жуковский\n"
        f"🕒 <b>Режим работы:</b> ежедневно с 12:00 до 02:00 (пт-сб до 04:00)\n\n"
        f"Ждем вас в гости! 🖤"
    )
    await callback.message.answer(about_text, parse_mode="HTML")

@router.message(F.text == "💳 Мой баланс")
async def show_balance(message: Message):
    user_data = await get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    balance = user_data["balance"]
    
    text = (
        f"💳 <b>Ваш текущий баланс:</b>\n\n"
        f"⭐ <b>{balance}</b> баллов\n\n"
        f"<i>Покажите ваш ID кассиру для начисления или списания баллов.</i>"
    )
    await message.answer(text, reply_markup=get_client_keyboard(), parse_mode="HTML")

@router.message(F.text == "🆔 Мой ID")
async def show_my_id(message: Message):
    user = message.from_user
    text = (
        f"🆔 <b>Ваши данные для кассира:</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Имя: {user.full_name}\n"
        f"@{user.username if user.username else 'отсутствует'}\n\n"
        f"<i>Сообщите этот ID кассиру при покупке.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📜 История баллов")
async def show_history(message: Message):
    transactions = await get_user_transactions(message.from_user.id, limit=10)
    if not transactions:
        await message.answer("📜 У вас пока нет истории операций с баллами.", reply_markup=get_client_keyboard())
        return
    
    text = "📜 <b>Последние операции по вашему счету:</b>\n\n"
    for tx in transactions:
        sign = "+" if tx["amount"] > 0 else ""
        text += f"• <b>{sign}{tx['amount']}</b> баллов — {tx['description']} <i>({tx['created_at']})</i>\n"
    
    await message.answer(text, reply_markup=get_client_keyboard(), parse_mode="HTML")

@router.message(F.text == "ℹ️ О баллах")
async def show_about(message: Message):
    text = (
        f"ℹ️ <b>О нашей программе лояльности:</b>\n\n"
        f"• За каждую покупку вам начисляются бонусные баллы.\n"
        f"• 1 балл = 1 рубль.\n"
        f"• Вы можете оплачивать баллами до 50% стоимости заказа.\n\n"
        f"Ждем вас в нашем заведении! 🌟"
    )
    await message.answer(text, reply_markup=get_client_keyboard(), parse_mode="HTML")
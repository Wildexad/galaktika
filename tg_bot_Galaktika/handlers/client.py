from aiogram import Router, F
import os

from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from database import get_or_create_user, get_user_transactions, update_user_activity

router = Router()

def get_client_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Мой баланс"), KeyboardButton(text="📜 История баллов")],
            [KeyboardButton(text="🆔 Мой ID"), KeyboardButton(text="ℹ️ О баллах")],
            [KeyboardButton(text="📅 Забронировать")]
        ],
        resize_keyboard=True
    )

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from handlers.admin import get_admin_ids

class BookingStates(StatesGroup):
    waiting_for_details = State()

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

@router.message(F.text == "📅 Забронировать")
async def start_booking(message: Message, state: FSMContext):
    await state.set_state(BookingStates.waiting_for_details)
    text = (
        f"📅 <b>Бронирование столика</b>\n\n"
        f"Пожалуйста, напишите детали брони одним сообщением:\n"
        f"• Дата и время\n"
        f"• Количество человек\n"
        f"• Ваше имя и контактный телефон\n\n"
        f"Пример записи:\n01.01.2025 16:05 \n3 \nАндрей \n+7(987)654-32-10\n\n"
        f"<i>(Или отправьте слово 'отмена' для выхода)</i>"
    )
    await message.answer(text, reply_markup=get_client_keyboard(), parse_mode="HTML")

@router.message(BookingStates.waiting_for_details)
async def process_booking_details(message: Message, state: FSMContext):
    if message.text and message.text.strip().lower() in ["отмена", "cancel", "/cancel"]:
        await state.clear()
        await message.answer("❌ Бронирование отменено.", reply_markup=get_client_keyboard())
        return

    details = message.text
    if not details:
        await message.answer("⚠️ Пожалуйста, отправьте текстовое описание брони.")
        return

    await state.clear()
    user = message.from_user
    username_str = f"@{user.username}" if user.username else "нет username"
    
    admin_text = (
        f"🔔 <b>Новая заявка на бронирование!</b>\n\n"
        f"👤 <b>Клиент:</b> {user.full_name} ({username_str})\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"📝 <b>Детали:</b>\n{details}"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"book_yes_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"book_no_{user.id}")
        ]
    ])

    admins = get_admin_ids()
    if not admins:
        await message.answer("⚠️ В настоящий момент администраторы не настроены в системе. Пожалуйста, позвоните нам напрямую.", reply_markup=get_client_keyboard())
        return

    sent_count = 0
    for admin_id in admins:
        try:
            await message.bot.send_message(admin_id, admin_text, reply_markup=admin_kb, parse_mode="HTML")
            sent_count += 1
        except Exception:
            pass

    if sent_count > 0:
        await message.answer("✅ Ваша заявка на бронирование успешно отправлена администраторам! Ожидайте подтверждения.", reply_markup=get_client_keyboard())
    else:
        await message.answer("❌ Не удалось отправить заявку администраторам. Пожалуйста, свяжитесь с нами по телефону +7 (999) 000-00-00.", reply_markup=get_client_keyboard())

@router.callback_query(F.data.startswith("book_"))
async def cb_booking_decision(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    
    action = parts[1] # yes or no
    client_id = int(parts[2])
    
    admins = get_admin_ids()
    if callback.from_user.id not in admins:
        await callback.answer("⛔ У вас нет прав администратора.", show_alert=True)
        return

    await callback.answer()

    if action == "yes":
        try:
            await callback.bot.send_message(
                client_id, 
                "🎉 <b>Ваша бронь подтверждена администратором!</b> Ждем вас в нашем лаунж-баре! 🍸",
                parse_mode="HTML"
            )
            await callback.message.edit_text(callback.message.text + "\n\n<b>✅ Статус: БРОНЬ ПОДТВЕРЖДЕНА</b>", parse_mode="HTML")
        except Exception:
            await callback.message.answer("⚠️ Не удалось отправить уведомление клиенту (возможно, он заблокировал бота).")
    else:
        phone_contact = os.getenv("CONTACT_PHONE", "+7 (999) 000-00-00")
        try:
            await callback.bot.send_message(
                client_id, 
                f"❌ К сожалению, забронировать столик на выбранное время не удалось.\n\n📞 Пожалуйста, свяжитесь с нами для уточнения деталей по телефону: <b>{phone_contact}</b>",
                parse_mode="HTML"
            )
            await callback.message.edit_text(callback.message.text + "\n\n<b>❌ Статус: БРОНЬ ОТКЛОНЕНА</b>", parse_mode="HTML")
        except Exception:
            await callback.message.answer("⚠️ Не удалось отправить уведомление клиенту.")

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
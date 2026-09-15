import os
import asyncio
from dotenv import load_dotenv
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import get_user_by_id, update_balance, get_user_transactions, get_all_users

router = Router()

def get_admin_ids():
    load_dotenv(override=True)
    admin_str = os.getenv("ADMIN_IDS", "")
    if not admin_str:
        return []
    try:
        ids = []
        for uid in admin_str.split(","):
            cleaned = uid.strip().strip("'\"")
            if cleaned.isdigit():
                ids.append(int(cleaned))
        return ids
    except ValueError:
        return []

class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        admins = get_admin_ids()
        return user_id in admins

class NotAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        admins = get_admin_ids()
        return user_id not in admins

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_description = State()
    waiting_for_broadcast = State()

def get_admin_main_kb():
    # Hosted Telegram WebApp QR scanner page or fallback custom URL
    webapp_url = os.getenv("WEBAPP_SCANNER_URL", "https://tg-qr-scanner.vercel.app")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📷 Сканировать QR", web_app=WebAppInfo(url=webapp_url))
        ],
        [
            InlineKeyboardButton(text="➕ Начислить", callback_data="adm_add"),
            InlineKeyboardButton(text="➖ Списать", callback_data="adm_sub")
        ],
        [
            InlineKeyboardButton(text="👤 Проверить баланс", callback_data="adm_info"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")
        ]
    ])

async def show_client_card_for_admin(message: Message, target_user_id: int):
    user = await get_user_by_id(target_user_id)
    if not user:
        await message.answer(f"❌ Клиент с ID <code>{target_user_id}</code> не найден в базе данных.", parse_mode="HTML")
        return
    
    txs = await get_user_transactions(target_user_id, limit=5)
    tx_text = "\n".join([f"• {'+' if t['amount'] > 0 else ''}{t['amount']} б. — {t['description']} <i>({t['created_at']})</i>" for t in txs]) or "Нет операций"
    
    card_text = (
        f"👤 <b>Карточка клиента:</b>\n\n"
        f"Имя: <b>{user['full_name']}</b>\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Telegram: @{user['username'] if user['username'] else 'отсутствует'}\n"
        f"⭐ <b>Текущий баланс:</b> {user['balance']} баллов\n\n"
        f"📜 <b>Последние 5 операций:</b>\n{tx_text}"
    )
    
    client_action_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Начислить", callback_data=f"adm_direct_add_{target_user_id}"),
            InlineKeyboardButton(text="➖ Списать", callback_data=f"adm_direct_sub_{target_user_id}")
        ],
        [
            InlineKeyboardButton(text="🛠 Главное меню", callback_data="adm_main")
        ]
    ])
    
    await message.answer(card_text, reply_markup=client_action_kb, parse_mode="HTML")

@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 <b>Панель кассира / администратора:</b>\nВыберите действие:", reply_markup=get_admin_main_kb(), parse_mode="HTML")


@router.message(Command("admin"), NotAdmin())
async def cmd_admin_denied(message: Message):
    user_id = message.from_user.id
    admins = get_admin_ids()
    print(f"⚠️ Доступ запрещен для пользователя {user_id}. Список админов в окружении: {admins}")
    await message.answer(f"⛔ У вас нет прав администратора.", parse_mode="HTML")

@router.callback_query(F.data == "adm_broadcast", IsAdmin())
async def cb_admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить рассылку", callback_data="adm_cancel_broadcast")]
    ])
    await callback.message.edit_text(
        "📢 <b>Режим рассылки сообщений</b>\n\n"
        "Отправьте текст или медиа-сообщение (фото, видео, документ), которое увидят ВСЕ зарегистрированные клиенты.\n\n"
        "<i>Для отмены нажмите кнопку ниже или отправьте слово 'отмена'.</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "adm_cancel_broadcast", IsAdmin())
async def cb_admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена.", reply_markup=get_admin_main_kb())
    await callback.answer()

@router.callback_query(F.data == "adm_main", IsAdmin())
async def cb_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 <b>Панель кассира / администратора:</b>\nВыберите действие:", reply_markup=get_admin_main_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("adm_direct_"), IsAdmin())
async def cb_admin_direct(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 4:
        return
    action = parts[2] # add or sub
    target_uid = int(parts[3])
    
    await state.update_data(action=action, uid=target_uid)
    await state.set_state(AdminStates.waiting_for_amount)
    
    act_title = "начисления" if action == "add" else "списания"
    await callback.message.answer(
        f"⭐ Режим <b>{act_title}</b> для клиента <code>{target_uid}</code>.\n\n"
        f"Введите сумму баллов (например, <code>100</code>):",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(F.web_app_data, IsAdmin())
async def process_web_app_qr(message: Message):
    data_str = message.web_app_data.data.strip()
    target_id = None
    if "user_" in data_str:
        try:
            target_id = int(data_str.split("user_")[1].split("&")[0].split("?")[0])
        except (ValueError, IndexError):
            pass
    elif data_str.isdigit():
        target_id = int(data_str)
        
    if target_id:
        await show_client_card_for_admin(message, target_id)
    else:
        await message.answer(f"⚠️ Не удалось распознать ID клиента из QR-кода: <code>{data_str}</code>", parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_"), IsAdmin())
async def cb_admin(callback: CallbackQuery, state: FSMContext):

    parts = callback.data.split("_")
    if len(parts) < 2:
        return
    action = parts[1]
    
    if action not in ["add", "sub", "info"]:
        return
        
    await state.update_data(action=action)
    await state.set_state(AdminStates.waiting_for_user_id)
    
    names = {"add": "начисления", "sub": "списания", "info": "проверки"}
    await callback.message.edit_text(
        f"👤 Режим: <b>{names.get(action)}</b>\n\nВведите <b>Telegram ID</b> клиента или перешлите его сообщение:",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("adm_"), NotAdmin())
async def cb_admin_denied(callback: CallbackQuery):
    await callback.answer("⛔ Нет прав.", show_alert=True)

@router.message(AdminStates.waiting_for_broadcast, IsAdmin())
async def state_process_broadcast(message: Message, state: FSMContext):
    if message.text and message.text.strip().lower() in ["отмена", "cancel", "/cancel"]:
        await state.clear()
        await message.answer("❌ Рассылка отменена.", reply_markup=get_admin_main_kb())
        return

    users = await get_all_users()
    if not users:
        await state.clear()
        await message.answer("⚠️ В базе данных пока нет зарегистрированных клиентов.", reply_markup=get_admin_main_kb())
        return

    await state.clear()
    status_msg = await message.answer(f"⏳ Отправка рассылки для <b>{len(users)}</b> пользователей...", parse_mode="HTML")

    success = 0
    blocked = 0
    failed = 0

    for user in users:
        uid = user["user_id"]
        try:
            await message.send_copy(chat_id=uid)
            success += 1
        except Exception as e:
            err_str = str(e).lower()
            if "forbidden" in err_str or "blocked" in err_str or "deactivated" in err_str:
                blocked += 1
            else:
                failed += 1
        
        await asyncio.sleep(0.05) # Prevent hitting Telegram rate limit

    report = (
        f"✅ <b>Рассылка успешно завершена!</b>\n\n"
        f"📊 <b>Результаты:</b>\n"
        f"• Доставлено: <b>{success}</b>\n"
        f"• Заблокировали бота: <b>{blocked}</b>\n"
        f"• Не удалось отправить: <b>{failed}</b>\n"
        f"• Всего пользователей: <b>{len(users)}</b>"
    )
    await status_msg.edit_text(report, parse_mode="HTML")

@router.message(AdminStates.waiting_for_user_id, IsAdmin())
async def state_user_id(message: Message, state: FSMContext):
    uid = message.forward_from.id if message.forward_from else (int(message.text.strip()) if message.text and message.text.strip().isdigit() else None)
    if not uid:
        await message.answer("⚠️ Введите числовой Telegram ID или перешлите сообщение.")
        return
    
    data = await state.get_data()
    action = data.get("action")
    user = await get_user_by_id(uid)
    
    if not user and action != "info":
        await message.answer(f"❌ Пользователь с ID <code>{uid}</code> не запущен в боте.", parse_mode="HTML")
        await state.clear()
        return
    
    if action == "info":
        if not user:
            await message.answer(f"❌ Пользователь с ID <code>{uid}</code> не найден.", parse_mode="HTML")
        else:
            txs = await get_user_transactions(uid, limit=5)
            tx_text = "\n".join([f"• {t['amount']} б. — {t['description']} ({t['created_at']})" for t in txs]) or "Нет операций"
            await message.answer(f"👤 <b>Клиент:</b> {user['full_name']} (<code>{uid}</code>)\n⭐ <b>Баланс:</b> {user['balance']} баллов\n\n📜 <b>История:</b>\n{tx_text}", parse_mode="HTML")
        await state.clear()
        return
    
    await state.update_data(uid=uid)
    await state.set_state(AdminStates.waiting_for_amount)
    await message.answer(f"⭐ Введите сумму для {'начисления' if action == 'add' else 'списания'} (например, <code>100</code>):", parse_mode="HTML")

@router.message(AdminStates.waiting_for_amount, IsAdmin())
async def state_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return
    amount = int(message.text.strip())
    if amount <= 0:
        await message.answer("⚠️ Сумма должна быть > 0.")
        return
    
    await state.update_data(amount=amount)
    await state.set_state(AdminStates.waiting_for_description)
    await message.answer("📝 Введите описание (например, <i>Кофе</i>) или отправьте <code>-</code>:", parse_mode="HTML")

@router.message(AdminStates.waiting_for_description, IsAdmin())
async def state_desc(message: Message, state: FSMContext):
    desc = message.text.strip() if message.text and message.text.strip() != "-" else "Операция"
    data = await state.get_data()
    action, uid, amount = data.get("action"), data.get("uid"), data.get("amount")
    
    tx_amt = amount if action == "add" else -amount
    new_bal, err = await update_balance(uid, message.from_user.id, tx_amt, desc)
    if err:
        await message.answer(f"❌ Ошибка: {err}")
        await state.clear()
        return
    
    title = "начислено" if action == "add" else "списано"
    sign = "+" if action == "add" else "-"
    await message.answer(f"✅ Успешно {title} <b>{sign}{amount}</b> баллов!\n👤 ID: <code>{uid}</code>\n⭐ Баланс: <b>{new_bal}</b>", parse_mode="HTML")
    
    try:
        msg = f"🎉 Вам начислено <b>+{amount}</b> баллов!" if action == "add" else f"🛍 Списано <b>-{amount}</b> баллов."
        await message.bot.send_message(uid, f"{msg}\n💳 Баланс: <b>{new_bal}</b>", parse_mode="HTML")
    except Exception:
        pass
    
    await state.clear()

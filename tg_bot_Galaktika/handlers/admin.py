import os
from dotenv import load_dotenv
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import get_user_by_id, update_balance, get_user_transactions

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

@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Начислить", callback_data="adm_add"),
            InlineKeyboardButton(text="➖ Списать", callback_data="adm_sub")
        ],
        [
            InlineKeyboardButton(text="👤 Проверить баланс", callback_data="adm_info")
        ]
    ])
    await message.answer("🛠 <b>Панель кассира:</b>\nВыберите действие:", reply_markup=kb, parse_mode="HTML")

@router.message(Command("admin"), NotAdmin())
async def cmd_admin_denied(message: Message):
    user_id = message.from_user.id
    admins = get_admin_ids()
    print(f"⚠️ Доступ запрещен для пользователя {user_id}. Список админов в окружении: {admins}")
    await message.answer(f"⛔ У вас нет прав администратора.", parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_"), IsAdmin())
async def cb_admin(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
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

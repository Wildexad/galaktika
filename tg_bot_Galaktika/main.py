import asyncio
import logging
import sys
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from database import init_db, get_inactive_users, update_user_reminder_time
from handlers import client, admin

load_dotenv(override=True)

async def inactivity_reminder_loop(bot: Bot):
    """
    Фоновая задача: периодически (раз в 6 часов) проверяет клиентов, 
    у которых не было активности более 7 дней, и отправляет им вежливое напоминание.
    """
    await asyncio.sleep(10) # Даем боту стартовать
    while True:
        try:
            inactive_users = await get_inactive_users(days=7)
            if inactive_users:
                logging.info(f"⏰ Найдено {len(inactive_users)} неактивных клиентов (>7 дней). Отправка напоминаний...")
                for user in inactive_users:
                    uid = user["user_id"]
                    name = user["full_name"]
                    bal = user["balance"]
                    
                    reminder_text = (
                        f"👋 <b>Здравствуйте, {name}!</b>\n\n"
                        f"Прошло уже больше недели с вашего последнего визита в <b>Galaktika Lounge</b>! 🍸💨\n\n"
                        f"⭐ На вашем счету <b>{bal} баллов</b>, которые вы можете списать при следующем заказе.\n"
                        f"Не желаете заглянуть к нам сегодня на чашечку авторского чая или дымный коктейль? ✨\n\n"
                        f"📍 г. Жуковский | Ждем вас в гости! 🖤"
                    )
                    
                    try:
                        await bot.send_message(uid, reminder_text, parse_mode="HTML")
                        await update_user_reminder_time(uid)
                        logging.info(f"✅ Напоминание успешно отправлено пользователю {uid}")
                    except Exception as e:
                        logging.warning(f"⚠️ Не удалось отправить напоминание пользователю {uid}: {e}")
                        # Отмечаем, чтобы не пытаться отправлять каждую итерацию при блокировке
                        await update_user_reminder_time(uid)
                    
                    await asyncio.sleep(0.1) # Задержка для предотвращения флуда
        except Exception as e:
            logging.error(f"❌ Ошибка в фоновом цикле напоминаний: {e}")
        
        # Проверка каждые 6 часов (21600 сек)
        await asyncio.sleep(6 * 3600)

async def main():
    token = os.getenv("BOT_TOKEN")
    if not token or token.startswith("7500000000:"):
        print("⚠️ ВНИМАНИЕ: Пожалуйста, укажите реальный BOT_TOKEN в файле .env перед запуском бота!")
    
    # Initialize database
    await init_db()
    
    # Optional proxy support (e.g. socks5://user:pass@host:port or http://host:port)
    proxy_url = os.getenv("PROXY_URL")
    session = AiohttpSession(proxy=proxy_url) if proxy_url else None

    
    bot = Bot(token=token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Include routers
    dp.include_router(admin.router)
    dp.include_router(client.router)
    
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print("🤖 Бот программы лояльности запущен и готов к работе...")

    
    # Запускаем фоновую задачу проверки неактивных клиентов
    asyncio.create_task(inactivity_reminder_loop(bot))
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")

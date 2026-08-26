import asyncio
import logging
import sys
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from database import init_db
from handlers import client, admin

load_dotenv(override=True)

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
    dp.include_router(client.runtime if hasattr(client, 'runtime') else client.router) # client.router
    
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    print("🤖 Бот программы лояльности запущен и готов к работе...")
    
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

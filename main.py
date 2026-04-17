import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from engine import load_system
from handlers import router

async def main():
    if load_system():
        print("bot has ready")
        
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
        dp = Dispatcher()
        
        #подключаем роутеры
        dp.include_router(router)
        
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
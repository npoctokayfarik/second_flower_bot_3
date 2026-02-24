import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import load_config
from .db import DB
from .handlers_user import user_router
from .handlers_admin import admin_router

async def main():
    cfg = load_config()
    db = DB(cfg.db_path)
    await db.init()

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # DI (чтобы хендлеры получали db/admin_ids/channel_id параметрами)
    dp["db"] = db
    dp["admin_ids"] = cfg.admin_ids
    dp["channel_id"] = cfg.channel_id

    dp.include_router(user_router)
    dp.include_router(admin_router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
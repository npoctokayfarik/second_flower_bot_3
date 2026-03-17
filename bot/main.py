import asyncio
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import load_config
from .db import DB
from .handlers_user import user_router
from .handlers_admin import admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def health(_: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_health_server(port: int) -> None:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Health server started on :{port}")


async def main() -> None:
    cfg = load_config()

    db = DB(cfg.db_path)
    await db.init()

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    @dp.update.outer_middleware()
    async def inject(handler, event, data):
        data["db"] = db
        data["admin_ids"] = cfg.admin_ids
        data["channel_id"] = cfg.channel_id
        return await handler(event, data)

    dp.include_router(admin_router)
    dp.include_router(user_router)

    await start_health_server(cfg.port)

    print("🤖 Bot polling started")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
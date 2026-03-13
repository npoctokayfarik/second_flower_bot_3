import os
import asyncio
import traceback
from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from .db import DB
from .handlers_user import user_router
from .handlers_admin import admin_router


def parse_admin_ids(raw: str) -> set[int]:
    raw = (raw or "").replace(" ", "")
    if not raw:
        return set()

    out = set()
    for x in raw.split(","):
        if not x:
            continue
        try:
            out.add(int(x))
        except ValueError:
            pass
    return out


async def health(request: web.Request):
    return web.json_response({"ok": True})


async def start_web_server(port: int):
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    print(f"🌐 Health server started on :{port}")


async def main():
    try:
        load_dotenv()

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        channel_id_raw = os.getenv("CHANNEL_ID", "").strip()
        admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
        db_path = os.getenv("DATABASE_PATH", "data/bot.db").strip()
        port = int(os.getenv("PORT", "10000"))

        missing = []
        if not bot_token:
            missing.append("BOT_TOKEN")
        if not channel_id_raw:
            missing.append("CHANNEL_ID")
        if not admin_ids_raw:
            missing.append("ADMIN_IDS")

        if missing:
            print("❌ Missing settings:", ", ".join(missing))
            raise RuntimeError("ENV is not set")

        channel_id = int(channel_id_raw)
        admin_ids = parse_admin_ids(admin_ids_raw)

        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        db = DB(db_path)
        await db.init()

        bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        dp = Dispatcher()
        dp.include_router(user_router)
        dp.include_router(admin_router)

        async def inject(handler, event, data):
            data["db"] = db
            data["admin_ids"] = admin_ids
            data["channel_id"] = channel_id
            return await handler(event, data)

        dp.update.middleware(inject)

        await bot.delete_webhook(drop_pending_updates=True)
        await start_web_server(port)
        print("🤖 Bot polling started")
        await dp.start_polling(bot)

    except Exception:
        print("💥 APP CRASHED:")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
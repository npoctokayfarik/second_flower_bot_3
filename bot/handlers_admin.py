from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from .db import DB
from .keyboards import kb_sold
from .utils import build_media_group
from .texts import mark_sold_caption

admin_router = Router()

def is_admin(user_id: int, admin_ids: set[int]) -> bool:
    return user_id in admin_ids

@admin_router.message(Command("admin"))
async def admin_panel(m: Message, db: DB, admin_ids: set[int]):
    if not is_admin(m.from_user.id, admin_ids):
        return await m.answer("Ты не админ 😅")
    pend = await db.pending_listings()
    if not pend:
        return await m.answer("Заявок нет. Красота ✨")
    txt = "Заявки (последние 20):\n" + "\n".join([f"• ID {x.id} — от {x.user_id}" for x in pend])
    await m.answer(txt)

@admin_router.callback_query(F.data.startswith("admin_publish:"))
async def admin_publish(cb: CallbackQuery, db: DB, admin_ids: set[int], channel_id: int):
    if not is_admin(cb.from_user.id, admin_ids):
        return await cb.answer("Не админ", show_alert=True)

    listing_id = int(cb.data.split(":")[1])
    listing = await db.get_listing(listing_id)
    if not listing:
        return await cb.answer("Не найдено", show_alert=True)
    if listing.status != "pending":
        return await cb.answer(f"Статус: {listing.status}", show_alert=True)

    await cb.answer("Публикую...")

    import json
    media = json.loads(listing.media_json)
    group = build_media_group(media)

    # caption на первое медиа
    group[0].caption = listing.caption
    group[0].parse_mode = "HTML"

    # 1) альбом в канал
    msgs = await cb.bot.send_media_group(chat_id=channel_id, media=group)
    first_msg_id = msgs[0].message_id

    # 2) отдельное сообщение с кнопкой "Продано"
    control = await cb.bot.send_message(
        chat_id=channel_id,
        text=f"Управление объявлением ID {listing_id}:",
        reply_markup=kb_sold(listing_id)
    )
    control_msg_id = control.message_id

    await db.set_published(listing_id, first_msg_id, control_msg_id)

    await cb.message.answer(f"✅ Опубликовано в канал.\nID: {listing_id}")
    await cb.message.edit_reply_markup(reply_markup=None)

@admin_router.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject(cb: CallbackQuery, db: DB, admin_ids: set[int]):
    if not is_admin(cb.from_user.id, admin_ids):
        return await cb.answer("Не админ", show_alert=True)

    listing_id = int(cb.data.split(":")[1])
    listing = await db.get_listing(listing_id)
    if not listing:
        return await cb.answer("Не найдено", show_alert=True)

    await db.set_rejected(listing_id)
    await cb.answer("Отклонено")
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(f"❌ Отклонено. ID: {listing_id}")

@admin_router.callback_query(F.data.startswith("sold:"))
async def sold(cb: CallbackQuery, db: DB, channel_id: int):
    listing_id = int(cb.data.split(":")[1])
    listing = await db.get_listing(listing_id)
    if not listing:
        return await cb.answer("Не найдено", show_alert=True)

    if listing.status == "sold":
        return await cb.answer("Уже продано ✅", show_alert=True)

    if listing.status != "published" or not listing.channel_first_message_id:
        return await cb.answer("Ещё не опубликовано/нет данных", show_alert=True)

    new_caption = mark_sold_caption(listing.caption, remove_contacts=True)

    # редактируем подпись первого сообщения альбома
    await cb.bot.edit_message_caption(
        chat_id=channel_id,
        message_id=listing.channel_first_message_id,
        caption=new_caption,
        parse_mode="HTML",
    )

    # обновим control-message и уберём кнопку
    if listing.channel_control_message_id:
        await cb.bot.edit_message_text(
            chat_id=channel_id,
            message_id=listing.channel_control_message_id,
            text=f"Объявление ID {listing_id}: ПРОДАНО ✅",
            reply_markup=None
        )

    await db.set_sold(listing_id)
    await cb.answer("Отмечено как ПРОДАНО ✅", show_alert=True)
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from .db import DB
from .utils import build_media_group
from .keyboards import (
    kb_open_bot_for_buy,
    kb_admin_payout,
    kb_seller_send_card,
)
from .texts import mark_sold_caption, fmt_sum, AD_FEE

admin_router = Router()


def is_admin(user_id: int, admin_ids: set[int]) -> bool:
    return user_id in admin_ids


@admin_router.message(Command("set_examples"))
async def cmd_set_examples(m: Message, db: DB, admin_ids: set[int]):
    if not is_admin(m.from_user.id, admin_ids):
        return
    await m.answer("Скинь 3 фото примера. Я сохраню последние 3.")


@admin_router.message(Command("set_admin_card"))
async def set_admin_card(m: Message, db: DB, admin_ids: set[int]):
    if not is_admin(m.from_user.id, admin_ids):
        return
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Используй так:\n/set_admin_card 9860040120797168")

    card = "".join(ch for ch in parts[1] if ch.isdigit())
    if len(card) != 16:
        return await m.answer("Нужен номер карты из 16 цифр")

    await db.set_setting("admin_card_number", card)
    await m.answer(f"✅ Карта администратора сохранена:\n{card}")


@admin_router.message(Command("set_admin_name"))
async def set_admin_name(m: Message, db: DB, admin_ids: set[int]):
    if not is_admin(m.from_user.id, admin_ids):
        return
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Используй так:\n/set_admin_name NURLAN ADMIN")

    holder = parts[1].strip()
    await db.set_setting("admin_card_holder", holder)
    await m.answer(f"✅ Имя получателя сохранено:\n{holder}")


@admin_router.message(F.photo)
async def catch_examples(m: Message, db: DB, admin_ids: set[int]):
    if not is_admin(m.from_user.id, admin_ids):
        return

    raw = await db.get_setting("examples_buffer") or "[]"
    try:
        buf = json.loads(raw)
        if not isinstance(buf, list):
            buf = []
    except Exception:
        buf = []

    buf.append(m.photo[-1].file_id)
    buf = buf[-3:]

    await db.set_setting("examples_buffer", json.dumps(buf, ensure_ascii=False))

    if len(buf) < 3:
        await m.answer(f"Ок, принято ({len(buf)}/3)")
        return

    await db.set_examples(buf)
    await db.set_setting("examples_buffer", "[]")
    await m.answer("✅ Примеры сохранены. Теперь /start покажет 3 фото.")


@admin_router.callback_query(F.data.startswith("admin_publish:"))
async def admin_publish(cb: CallbackQuery, db: DB, admin_ids: set[int], channel_id: int):
    if not is_admin(cb.from_user.id, admin_ids):
        try:
            await cb.answer("Нет доступа", show_alert=True)
        except Exception:
            pass
        return

    try:
        await cb.answer()
    except Exception:
        pass

    listing_id = int(cb.data.split(":", 1)[1])
    listing = await db.get_listing(listing_id)
    if not listing:
        return await cb.message.answer("Не найдено")

    media_items = json.loads(listing.media_json)
    if not media_items:
        return await cb.message.answer("Нет медиа")

    me = await cb.bot.get_me()
    bot_username = me.username or ""
    buy_markup = kb_open_bot_for_buy(bot_username, listing_id) if bot_username else None

    first_message_id = None

    # одно медиа = одно сообщение с кнопкой
    if len(media_items) == 1:
        item = media_items[0]
        media_type = item.get("type")
        file_id = item.get("file_id")

        try:
            if media_type == "photo":
                msg = await cb.bot.send_photo(
                    chat_id=channel_id,
                    photo=file_id,
                    caption=listing.public_caption,
                    parse_mode="HTML",
                    reply_markup=buy_markup,
                )
                first_message_id = msg.message_id

            elif media_type == "video":
                msg = await cb.bot.send_video(
                    chat_id=channel_id,
                    video=file_id,
                    caption=listing.public_caption,
                    parse_mode="HTML",
                    reply_markup=buy_markup,
                )
                first_message_id = msg.message_id
            else:
                return await cb.message.answer("Неизвестный тип медиа")

        except Exception as e:
            return await cb.message.answer(f"Ошибка публикации: {e}")

        await db.set_published(listing_id, first_message_id, first_message_id)
        return await cb.message.answer("✅ Опубликовано одним сообщением")

    # несколько медиа = первое с кнопкой, остальные альбомом
    first_item = media_items[0]
    rest_items = media_items[1:]

    try:
        if first_item.get("type") == "photo":
            first_msg = await cb.bot.send_photo(
                chat_id=channel_id,
                photo=first_item["file_id"],
                caption=listing.public_caption,
                parse_mode="HTML",
                reply_markup=buy_markup,
            )
            first_message_id = first_msg.message_id

        elif first_item.get("type") == "video":
            first_msg = await cb.bot.send_video(
                chat_id=channel_id,
                video=first_item["file_id"],
                caption=listing.public_caption,
                parse_mode="HTML",
                reply_markup=buy_markup,
            )
            first_message_id = first_msg.message_id
        else:
            return await cb.message.answer("Неизвестный тип первого медиа")

        if rest_items:
            group = build_media_group(rest_items)
            if group:
                await cb.bot.send_media_group(chat_id=channel_id, media=group)

        await db.set_published(listing_id, first_message_id, first_message_id)
        await cb.message.answer("✅ Опубликовано. Кнопка внутри объявления.")
    except Exception as e:
        await cb.message.answer(f"Ошибка публикации: {e}")


@admin_router.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject(cb: CallbackQuery, db: DB, admin_ids: set[int]):
    if not is_admin(cb.from_user.id, admin_ids):
        try:
            await cb.answer("Нет доступа", show_alert=True)
        except Exception:
            pass
        return

    try:
        await cb.answer()
    except Exception:
        pass

    listing_id = int(cb.data.split(":", 1)[1])
    listing = await db.get_listing(listing_id)
    if not listing:
        return await cb.message.answer("Не найдено")

    await db.set_rejected(listing_id)

    try:
        await cb.bot.send_message(
            chat_id=listing.user_id,
            text=(
                f"❌ Заявка отклонена (ID {listing_id}).\n"
                f"Стоимость размещения объявления: {fmt_sum(AD_FEE)} сум."
            )
        )
    except Exception:
        pass

    await cb.message.answer("Отклонено")


@admin_router.callback_query(F.data.startswith("deal_paid_confirm:"))
async def deal_paid_confirm(cb: CallbackQuery, db: DB, admin_ids: set[int]):
    if not is_admin(cb.from_user.id, admin_ids):
        try:
            await cb.answer("Нет доступа", show_alert=True)
        except Exception:
            pass
        return

    try:
        await cb.answer()
    except Exception:
        pass

    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")

    await db.confirm_buyer_paid(deal_id)

    try:
        await cb.bot.send_message(
            deal.seller_id,
            (
                f"✅ Оплата по сделке #{deal_id} подтверждена.\n"
                f"Сумма продажи: {fmt_sum(deal.price)} сум\n\n"
                f"Сначала отправь номер своей карты для выплаты."
            ),
            reply_markup=kb_seller_send_card(deal_id)
        )
    except Exception:
        pass

    try:
        await cb.bot.send_message(
            deal.buyer_id,
            f"✅ Администратор подтвердил оплату по сделке #{deal_id}."
        )
    except Exception:
        pass

    await cb.message.answer("Оплата подтверждена")


@admin_router.callback_query(F.data.startswith("deal_paid_reject:"))
async def deal_paid_reject(cb: CallbackQuery, db: DB, admin_ids: set[int]):
    if not is_admin(cb.from_user.id, admin_ids):
        try:
            await cb.answer("Нет доступа", show_alert=True)
        except Exception:
            pass
        return

    try:
        await cb.answer()
    except Exception:
        pass

    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")

    await db.reject_buyer_paid(deal_id)

    try:
        await cb.bot.send_message(
            deal.buyer_id,
            f"❌ Чек по сделке #{deal_id} не подтверждён. Отправь корректный чек заново."
        )
    except Exception:
        pass

    await cb.message.answer("Чек отклонён")


@admin_router.callback_query(F.data.startswith("deal_received_ok:"))
async def deal_received_ok(cb: CallbackQuery, db: DB, admin_ids: set[int]):
    try:
        await cb.answer()
    except Exception:
        pass

    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")

    if cb.from_user.id != deal.buyer_id:
        return await cb.message.answer("Это не твоя сделка")

    await db.set_buyer_confirmed(deal_id)

    for admin_id in admin_ids:
        try:
            text = (
                f"✅ Покупатель подтвердил получение по сделке #{deal_id}\n"
                f"К выплате продавцу: {fmt_sum(deal.seller_payout_amount)} сум\n"
                f"Карта продавца: {deal.seller_card or 'не отправлена'}"
            )
            await cb.bot.send_message(
                admin_id,
                text,
                reply_markup=kb_admin_payout(deal_id)
            )
        except Exception:
            pass

    await cb.message.answer("Спасибо, подтверждение принято ✅")


@admin_router.callback_query(F.data.startswith("deal_problem:"))
async def deal_problem(cb: CallbackQuery, db: DB, admin_ids: set[int]):
    try:
        await cb.answer()
    except Exception:
        pass

    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")

    if cb.from_user.id != deal.buyer_id:
        return await cb.message.answer("Это не твоя сделка")

    await db.set_problem(deal_id)

    for admin_id in admin_ids:
        try:
            await cb.bot.send_message(
                admin_id,
                f"⚠️ Проблема по сделке #{deal_id}. Нужна ручная проверка."
            )
        except Exception:
            pass

    await cb.message.answer("Администратор получил уведомление о проблеме ⚠️")


@admin_router.callback_query(F.data.startswith("deal_payout_done:"))
async def deal_payout_done(cb: CallbackQuery, db: DB, admin_ids: set[int], channel_id: int):
    if not is_admin(cb.from_user.id, admin_ids):
        try:
            await cb.answer("Нет доступа", show_alert=True)
        except Exception:
            pass
        return

    try:
        await cb.answer()
    except Exception:
        pass

    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")

    listing = await db.get_listing(deal.listing_id)
    if not listing:
        return await cb.message.answer("Объявление не найдено")

    await db.set_payout_done(deal_id)

    new_caption = mark_sold_caption(listing.public_caption)
    await db.set_listing_sold(listing.id, new_caption)

    if listing.channel_first_message_id:
        try:
            await cb.bot.edit_message_caption(
                chat_id=channel_id,
                message_id=listing.channel_first_message_id,
                caption=new_caption,
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception:
            try:
                await cb.bot.edit_message_reply_markup(
                    chat_id=channel_id,
                    message_id=listing.channel_first_message_id,
                    reply_markup=None
                )
            except Exception:
                pass

    try:
        await cb.bot.send_message(
            deal.seller_id,
            f"✅ Администратор отправил тебе выплату по сделке #{deal_id}\nСумма: {fmt_sum(deal.seller_payout_amount)} сум"
        )
    except Exception:
        pass

    try:
        await cb.bot.send_message(
            deal.buyer_id,
            f"✅ Сделка #{deal_id} завершена. Спасибо за покупку!"
        )
    except Exception:
        pass

    await cb.message.answer("Сделка закрыта, объявление помечено как ПРОДАНО ✅")
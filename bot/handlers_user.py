from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from .states import NewListing
from .texts import RULES_TEXT, build_caption
from .keyboards import kb_start, kb_confirm, kb_admin_review
from .db import DB

user_router = Router()

@user_router.message(CommandStart())
async def start(m: Message):
    await m.answer(RULES_TEXT, reply_markup=kb_start())

@user_router.callback_query(F.data == "example")
async def example(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "Пример правильной записки:\n"
        "SECOND FLOWERS\n"
        "24.02.2026 22:30\n\n"
        "Главное: чтобы было видно на ФОТО/ВИДЕО и совпадало."
    )

@user_router.callback_query(F.data == "new")
async def new(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Ок, создаём объявление ✍️\nНапиши название (например: Красивый букет):")
    await state.set_state(NewListing.title)

@user_router.callback_query(F.data == "restart_new")
async def restart(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Давай заново. Напиши название:")
    await state.set_state(NewListing.title)

@user_router.callback_query(F.data == "cancel_new")
async def cancel(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Ок, отменил ✅")

@user_router.message(NewListing.title)
async def st_title(m: Message, state: FSMContext):
    await state.update_data(title=m.text.strip())
    await m.answer("Регион? (например: Ташкент)")
    await state.set_state(NewListing.region)

@user_router.message(NewListing.region)
async def st_region(m: Message, state: FSMContext):
    await state.update_data(region=m.text.strip())
    await m.answer("Район? (например: Яккасарай)")
    await state.set_state(NewListing.district)

@user_router.message(NewListing.district)
async def st_district(m: Message, state: FSMContext):
    await state.update_data(district=m.text.strip())
    await m.answer("Свежесть? (например: Сегодня)")
    await state.set_state(NewListing.freshness)

@user_router.message(NewListing.freshness)
async def st_fresh(m: Message, state: FSMContext):
    await state.update_data(freshness=m.text.strip())
    await m.answer("Комментарий? (например: Подарили на день рождения)")
    await state.set_state(NewListing.comment)

@user_router.message(NewListing.comment)
async def st_comment(m: Message, state: FSMContext):
    await state.update_data(comment=m.text.strip())
    await m.answer("Цена (только число, без сум)? (например: 200000)")
    await state.set_state(NewListing.price)

@user_router.message(NewListing.price)
async def st_price(m: Message, state: FSMContext):
    price = m.text.strip().replace(" ", "")
    if not price.isdigit():
        return await m.answer("Нужно число 🙃 Например: 200000")
    await state.update_data(price=price)
    await m.answer("Контакты? (например: @sumu_1203 или номер)")
    await state.set_state(NewListing.contact)

@user_router.message(NewListing.contact)
async def st_contact(m: Message, state: FSMContext):
    await state.update_data(contact=m.text.strip())
    await state.update_data(media=[])
    await m.answer(
        "Теперь скинь фото/видео букета.\n"
        "Можно несколько (до 10). Когда закончишь — напиши: ГОТОВО"
    )
    await state.set_state(NewListing.media)

@user_router.message(NewListing.media, F.text.casefold() == "готово")
async def media_done(m: Message, state: FSMContext):
    data = await state.get_data()
    media = data.get("media", [])
    if not media:
        return await m.answer("Нужны хотя бы 1 фото или видео 🥲")

    caption = build_caption(
        title=data["title"],
        region=data["region"],
        district=data["district"],
        freshness=data["freshness"],
        comment=data["comment"],
        price=data["price"],
        contact=data["contact"],
    )
    await state.update_data(caption=caption)

    await m.answer(
        "Проверяй превью текста (так уйдёт в канал):\n\n"
        f"{caption}\n\n"
        "Если всё ок — отправляй на модерацию.",
        reply_markup=kb_confirm()
    )
    await state.set_state(NewListing.confirm)

@user_router.message(NewListing.media)
async def media_collect(m: Message, state: FSMContext):
    data = await state.get_data()
    media = data.get("media", [])
    if len(media) >= 10:
        return await m.answer("Максимум 10 медиа. Напиши: ГОТОВО")

    if m.photo:
        file_id = m.photo[-1].file_id
        media.append({"type": "photo", "file_id": file_id})
        await state.update_data(media=media)
        return await m.answer(f"Фото добавлено ✅ ({len(media)}/10). Ещё? Или напиши: ГОТОВО")

    if m.video:
        file_id = m.video.file_id
        media.append({"type": "video", "file_id": file_id})
        await state.update_data(media=media)
        return await m.answer(f"Видео добавлено ✅ ({len(media)}/10). Ещё? Или напиши: ГОТОВО")

    await m.answer("Скинь именно фото/видео, либо напиши: ГОТОВО")

@user_router.callback_query(F.data == "send_to_review")
async def send_to_review(cb: CallbackQuery, state: FSMContext, db: DB, admin_ids: set[int]):
    await cb.answer()
    data = await state.get_data()

    if not data.get("caption") or not data.get("media"):
        await cb.message.answer("Что-то не так с данными. Давай заново: /start")
        await state.clear()
        return

    listing_id = await db.create_listing(cb.from_user.id, data)
    await state.clear()

    # Админам сразу прилетает заявка с кнопками
    for admin_id in admin_ids:
        try:
            await cb.bot.send_message(
                chat_id=admin_id,
                text=f"Новая заявка ID {listing_id}\n\n{data['caption']}",
                reply_markup=kb_admin_review(listing_id)
            )
        except:
            pass

    await cb.message.answer(f"Заявка отправлена на модерацию ✅\nID: {listing_id}\nЖди апрув 😎")
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from .states import NewListing, BuyerDealProof, SellerCard, SellerDeliveryProof
from .texts import RULES_TEXT, build_public_caption, fmt_sum, AD_FEE
from .keyboards import (
    kb_start,
    kb_confirm,
    kb_request_phone,
    kb_region,
    kb_city,
    kb_district_tashkent,
    kb_finish_media,
    kb_buyer_send_receipt,
    kb_seller_send_card,
    kb_seller_send_delivery,
    kb_buyer_confirm_received,
    kb_admin_payment_confirm,
)
from .db import DB
from .utils import build_media_group

user_router = Router()

PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{7,}$")
CARD_RE = re.compile(r"^\d{16}$")
ADMIN_CARD = "9860040120797168"

REGION_NAME = {
    "krk": "Республика Каракалпакстан",
    "tash_city": "Ташкент (город)",
    "tash_obl": "Ташкентская область",
    "and": "Андижанская область",
    "bkh": "Бухарская область",
    "fer": "Ферганская область",
    "jiz": "Джизакская область",
    "khr": "Хорезмская область",
    "qsh": "Кашкадарьинская область",
    "nav": "Навоийская область",
    "nam": "Наманганская область",
    "sam": "Самаркандская область",
    "syr": "Сырдарьинская область",
    "sur": "Сурхандарьинская область",
    "other": "Другое",
}

CITY_NAME = {
    "nukus":"Нукус","khodjeyli":"Ходжейли","turtkul":"Турткуль","beruni":"Беруни","kungrad":"Кунград","moynaq":"Муйнак","chimbay":"Чимбай",
    "tashkent":"Ташкент","chirchiq":"Чирчик","angren":"Ангрен","almalyk":"Алмалык","bekabad":"Бекабад","yangiyul":"Янгиюль","gazalkent":"Газалкент",
    "andijan":"Андижан","asaka":"Асака","shahrikhan":"Шахрихан","khanabad":"Ханабад",
    "bukhara":"Бухара","kagan":"Каган","gijduvan":"Гиждуван",
    "fergana":"Фергана","kokand":"Коканд","margilan":"Маргилан","kuva":"Кува",
    "jizzakh":"Джизак","paxtakor":"Пахтакор",
    "urgench":"Ургенч","khiva":"Хива","hazorasp":"Хазарасп",
    "qarshi":"Карши","shahrisabz":"Шахрисабз","guzar":"Гузар",
    "navoi":"Навои","zarafshan":"Зарафшан","uchquduq":"Учкудук",
    "namangan":"Наманган","chust":"Чуст","pap":"Пап",
    "samarkand":"Самарканд","kattakurgan":"Каттакурган","urgut":"Ургут",
    "gulistan":"Гулистан","yangier":"Янгиер","shirin":"Ширин",
    "termez":"Термез","denau":"Денау","sherabad":"Шерабад",
    "other":"Другое",
}

DISTRICT_NAME = {
    "almazar":"Алмазар","bektemir":"Бектемир","mirabad":"Мирабад","mirzo_ulugbek":"Мирзо-Улугбек",
    "sergeli":"Сергелий","uchtepa":"Учтепа","chilanzar":"Чиланзар","shaykhontohur":"Шайхантахур",
    "yunusabad":"Юнусабад","yakkasaray":"Яккасарай","yashnabad":"Яшнабад","other":"Другое"
}


def digits_only(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def normalize_phone(raw: str) -> str:
    raw = (raw or "").strip()
    d = digits_only(raw)
    if d.startswith("998") and len(d) >= 12:
        return "+" + d[:12]
    if len(d) == 9:
        return "+998" + d
    if raw.startswith("+") and d.startswith("998") and len(d) >= 12:
        return "+" + d[:12]
    return raw


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(phone)) and digits_only(phone).startswith("998")


def parse_price_int(text: str) -> int | None:
    d = digits_only((text or "").strip())
    if not d:
        return None
    try:
        return int(d)
    except ValueError:
        return None


def extract_file_id_from_message(m: Message) -> tuple[str, str]:
    if m.photo:
        return m.photo[-1].file_id, "photo"
    if m.video:
        return m.video.file_id, "video"
    if m.document:
        return m.document.file_id, "document"
    return "", ""


async def safe_cb_answer(cb: CallbackQuery):
    try:
        await cb.answer()
    except Exception:
        pass


def mark_reserved_caption(public_caption: str) -> str:
    if "ЗАБРОНИРОВАНО" in public_caption:
        return public_caption
    return public_caption + "\n\n⏳ <b>ЗАБРОНИРОВАНО</b>"


@user_router.message(CommandStart())
async def start(m: Message, db: DB, channel_id: int):
    text = m.text or ""
    parts = text.split(maxsplit=1)
    start_arg = parts[1].strip() if len(parts) > 1 else ""

    photo_ids = await db.get_examples()
    if len(photo_ids) == 3:
        media = [InputMediaPhoto(media=pid) for pid in photo_ids]
        media[0].caption = "✅ Пример правильной записки"
        await m.bot.send_media_group(chat_id=m.chat.id, media=media)

    if start_arg.startswith("buy_"):
        try:
            listing_id = int(start_arg.replace("buy_", "", 1))
            listing = await db.get_listing(listing_id)
            if not listing:
                return await m.answer("❌ Объявление не найдено")

            if listing.status != "published":
                return await m.answer("❌ Этот букет уже забронирован или продан")

            if m.from_user.id == listing.user_id:
                return await m.answer("❌ Нельзя купить свой букет")

            active = await db.get_active_deal_by_listing(listing_id)
            if active:
                return await m.answer("❌ По этому букету уже идёт сделка")

            price = int(listing.price)

            deal_id = await db.create_deal(
                listing_id=listing.id,
                seller_id=listing.user_id,
                buyer_id=m.from_user.id,
                price=price,
                commission_amount=0,
                seller_payout_amount=price,
            )

            reserved_caption = mark_reserved_caption(listing.public_caption)
            await db.set_listing_reserved(listing.id, reserved_caption)

            if listing.channel_first_message_id:
                try:
                    await m.bot.edit_message_caption(
                        chat_id=channel_id,
                        message_id=listing.channel_first_message_id,
                        caption=reserved_caption,
                        parse_mode="HTML",
                        reply_markup=None
                    )
                except Exception:
                    try:
                        await m.bot.edit_message_reply_markup(
                            chat_id=channel_id,
                            message_id=listing.channel_first_message_id,
                            reply_markup=None
                        )
                    except Exception:
                        pass

            await m.answer(
                f"💳 Оплатите букет администрации\n\n"
                f"Сумма: <b>{fmt_sum(price)} сум</b>\n\n"
                f"Карта администратора:\n"
                f"<code>{ADMIN_CARD}</code>\n\n"
                f"После оплаты отправьте чек.",
                reply_markup=kb_buyer_send_receipt(deal_id)
            )

            try:
                await m.bot.send_message(
                    listing.user_id,
                    f"💐 Ваш букет забронирован!\n\nСделка ID: {deal_id}\nЖдём подтверждение оплаты."
                )
            except Exception:
                pass

            return
        except Exception as e:
            print("BUY ERROR:", e)
            return await m.answer("❌ Не удалось открыть сделку")

    await m.answer(RULES_TEXT, reply_markup=kb_start())


@user_router.callback_query(F.data == "donate")
async def donate(cb: CallbackQuery):
    await safe_cb_answer(cb)
    await cb.message.answer(
        "💝 <b>Поддержать проект Second Flowers</b>\n\n"
        "Если вам нравится наш сервис и вы хотите помочь развитию проекта,\n"
        "вы можете отправить любую сумму доната.\n\n"
        "💳 <b>Карта для доната:</b>\n"
        "<code>9860040120797168</code>\n\n"
        "Спасибо за поддержку ❤️"
    )


@user_router.callback_query(F.data == "new")
async def new(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    await state.clear()
    await cb.message.answer(
        f"📢 <b>Размещение объявления стоит {fmt_sum(AD_FEE)} сум</b>\n\n"
        f"Сначала создай объявление. После отправки заявки администратор подтвердит публикацию.\n\n"
        f"💳 Карта администратора: <b>{ADMIN_CARD}</b>"
    )
    await cb.message.answer("Название букета:")
    await state.set_state(NewListing.title)


@user_router.callback_query(F.data == "restart_new")
async def restart_new(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    await state.clear()
    await cb.message.answer("Название букета:")
    await state.set_state(NewListing.title)


@user_router.callback_query(F.data == "cancel_new")
async def cancel_new(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    await state.clear()
    await cb.message.answer("Ок ✅", reply_markup=ReplyKeyboardRemove())


@user_router.message(NewListing.title)
async def st_title(m: Message, state: FSMContext):
    await state.update_data(title=(m.text or "").strip())
    await m.answer("📍 Регион:", reply_markup=kb_region())
    await state.set_state(NewListing.region)


@user_router.callback_query(NewListing.region, F.data.startswith("region:"))
async def pick_region(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    code = cb.data.split(":", 1)[1]
    if code == "other":
        await cb.message.answer("Напиши регион:")
        return
    await state.update_data(region=REGION_NAME.get(code, code), region_code=code)
    await cb.message.answer("🏙️ Город:", reply_markup=kb_city(code))
    await state.set_state(NewListing.city)


@user_router.message(NewListing.region)
async def region_text(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt:
        return await m.answer("Напиши регион:")
    await state.update_data(region=txt, region_code="other")
    await m.answer("🏙️ Город:", reply_markup=kb_city("other"))
    await state.set_state(NewListing.city)


@user_router.callback_query(NewListing.city, F.data.startswith("city:"))
async def pick_city(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    code = cb.data.split(":", 1)[1]
    data = await state.get_data()
    region_code = data.get("region_code", "other")

    if code == "other":
        await cb.message.answer("Напиши город:")
        return

    city_name = CITY_NAME.get(code, code)
    await state.update_data(city=city_name)

    if region_code == "tash_city" and city_name == "Ташкент":
        await cb.message.answer("Район:", reply_markup=kb_district_tashkent())
        await state.set_state(NewListing.district)
    else:
        await state.update_data(district="")
        await cb.message.answer("Адрес (улица, дом, ориентир):")
        await state.set_state(NewListing.address)


@user_router.message(NewListing.city)
async def city_text(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt:
        return await m.answer("Напиши город:")
    await state.update_data(city=txt)

    data = await state.get_data()
    region_code = data.get("region_code", "other")

    if region_code == "tash_city" and txt.lower() == "ташкент":
        await m.answer("Район:", reply_markup=kb_district_tashkent())
        await state.set_state(NewListing.district)
    else:
        await state.update_data(district="")
        await m.answer("Адрес (улица, дом, ориентир):")
        await state.set_state(NewListing.address)


@user_router.callback_query(NewListing.district, F.data.startswith("district:"))
async def pick_district(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    code = cb.data.split(":", 1)[1]
    if code == "other":
        await cb.message.answer("Напиши район:")
        return
    await state.update_data(district=DISTRICT_NAME.get(code, code))
    await cb.message.answer("Адрес (улица, дом, ориентир):")
    await state.set_state(NewListing.address)


@user_router.message(NewListing.district)
async def district_text(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt:
        return await m.answer("Напиши район:")
    await state.update_data(district=txt)
    await m.answer("Адрес (улица, дом, ориентир):")
    await state.set_state(NewListing.address)


@user_router.message(NewListing.address)
async def st_address(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if not txt:
        return await m.answer("Адрес (улица, дом, ориентир):")
    await state.update_data(address=txt)
    await m.answer("Свежесть:")
    await state.set_state(NewListing.freshness)


@user_router.message(NewListing.freshness)
async def st_fresh(m: Message, state: FSMContext):
    await state.update_data(freshness=(m.text or "").strip())
    await m.answer("Комментарий:")
    await state.set_state(NewListing.comment)


@user_router.message(NewListing.comment)
async def st_comment(m: Message, state: FSMContext):
    await state.update_data(comment=(m.text or "").strip())
    await m.answer("Цена (сум):")
    await state.set_state(NewListing.price)


@user_router.message(NewListing.price)
async def st_price(m: Message, state: FSMContext):
    price_int = parse_price_int(m.text)
    if price_int is None or price_int <= 0:
        return await m.answer("Введи цену числом 🙂")

    await state.update_data(price=str(price_int))
    await m.answer(
        f"Стоимость размещения объявления: <b>{fmt_sum(AD_FEE)} сум</b>\n"
        f"После оплаты объявление будет опубликовано.\n\n"
        f"Отправь номер телефона:",
        reply_markup=kb_request_phone()
    )
    await state.set_state(NewListing.contact)


@user_router.message(NewListing.contact, F.contact)
async def st_contact_by_contact(m: Message, state: FSMContext):
    phone = normalize_phone(m.contact.phone_number if m.contact else "")
    if not is_valid_phone(phone):
        return await m.answer("Отправь номер телефона 🙂", reply_markup=kb_request_phone())

    await state.update_data(contact=phone, media=[])
    await m.answer("Отправь фото/видео\nПотом нажми ✅ Завершить", reply_markup=kb_finish_media())
    await m.answer("⬇️", reply_markup=ReplyKeyboardRemove())
    await state.set_state(NewListing.media)


@user_router.message(NewListing.contact)
async def st_contact_manual(m: Message, state: FSMContext):
    phone = normalize_phone(m.text or "")
    if not is_valid_phone(phone):
        return await m.answer("Отправь номер телефона 🙂", reply_markup=kb_request_phone())

    await state.update_data(contact=phone, media=[])
    await m.answer("Отправь фото/видео\nПотом нажми ✅ Завершить", reply_markup=kb_finish_media())
    await m.answer("⬇️", reply_markup=ReplyKeyboardRemove())
    await state.set_state(NewListing.media)


@user_router.message(NewListing.media)
async def media_collect(m: Message, state: FSMContext):
    data = await state.get_data()
    media = data.get("media", [])

    if len(media) >= 10:
        return await m.answer("Максимум 10", reply_markup=kb_finish_media())

    if m.photo:
        media.append({"type": "photo", "file_id": m.photo[-1].file_id})
        await state.update_data(media=media)
        return await m.answer(f"✅ Добавлено ({len(media)}/10)", reply_markup=kb_finish_media())

    if m.video:
        media.append({"type": "video", "file_id": m.video.file_id})
        await state.update_data(media=media)
        return await m.answer(f"✅ Добавлено ({len(media)}/10)", reply_markup=kb_finish_media())

    await m.answer("Отправь фото/видео или нажми ✅ Завершить", reply_markup=kb_finish_media())


@user_router.callback_query(NewListing.media, F.data == "finish_media")
async def finish_media(cb: CallbackQuery, state: FSMContext):
    await safe_cb_answer(cb)
    data = await state.get_data()
    media = data.get("media", [])
    if not media:
        return await cb.message.answer("Нужно хотя бы 1 фото/видео", reply_markup=kb_finish_media())

    district = (data.get("district") or "").strip()

    public_caption = build_public_caption(
        title=data["title"],
        region=data["region"],
        city=data["city"],
        district=district,
        address=data["address"],
        freshness=data["freshness"],
        comment=data["comment"],
        price=fmt_sum(int(data["price"])),
        phone=data["contact"],
        user_username=cb.from_user.username,
    )
    await state.update_data(public_caption=public_caption, district=district)
    await cb.message.answer("Проверь объявление:\n\n" + public_caption, reply_markup=kb_confirm())
    await state.set_state(NewListing.confirm)


@user_router.callback_query(F.data == "send_to_review")
async def send_to_review(cb: CallbackQuery, state: FSMContext, db: DB, admin_ids: set[int]):
    await safe_cb_answer(cb)
    data = await state.get_data()

    if data.get("district") is None:
        data["district"] = ""

    required_keys = ["public_caption", "media", "price", "contact", "region", "city", "address", "freshness", "title"]
    if any(not data.get(k) for k in required_keys):
        await cb.message.answer("Что-то сломалось. /start")
        await state.clear()
        return

    listing_id = await db.create_listing(
        user_id=cb.from_user.id,
        user_full_name=cb.from_user.full_name or "—",
        user_username=cb.from_user.username,
        data=data
    )
    await state.clear()

    from .texts import build_admin_info
    from .keyboards import kb_admin_review

    admin_info = build_admin_info(
        user_full_name=cb.from_user.full_name or "—",
        user_username=cb.from_user.username,
        user_id=cb.from_user.id,
        phone=data["contact"]
    )

    for admin_id in admin_ids:
        try:
            group = build_media_group(data["media"])
            if not group:
                continue
            group[0].caption = (
                f"Новая заявка ID {listing_id}\n\n"
                f"{admin_info}\n\n"
                f"Стоимость размещения: {fmt_sum(AD_FEE)} сум\n"
                f"Карта администратора: {ADMIN_CARD}\n\n"
                f"Пост в канал:\n{data['public_caption']}"
            )
            group[0].parse_mode = "HTML"
            await cb.bot.send_media_group(chat_id=admin_id, media=group)
            await cb.bot.send_message(
                chat_id=admin_id,
                text=f"Модерация заявки ID {listing_id}:",
                reply_markup=kb_admin_review(listing_id)
            )
        except Exception as e:
            print("SEND TO ADMIN ERROR:", e)

    await cb.message.answer(f"✅ Заявка отправлена\nID: {listing_id}")


@user_router.callback_query(F.data.startswith("deal_send_receipt:"))
async def deal_send_receipt(cb: CallbackQuery, state: FSMContext, db: DB):
    await safe_cb_answer(cb)
    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")
    if cb.from_user.id != deal.buyer_id:
        return await cb.message.answer("Это не твоя сделка")

    await state.update_data(deal_id=deal_id)
    await state.set_state(BuyerDealProof.waiting_proof)
    await cb.message.answer("Скинь чек оплаты фото/видео/документом")


@user_router.message(BuyerDealProof.waiting_proof)
async def buyer_send_receipt_file(m: Message, state: FSMContext, db: DB, admin_ids: set[int]):
    data = await state.get_data()
    deal_id = int(data["deal_id"])
    deal = await db.get_deal(deal_id)
    if not deal:
        await state.clear()
        return await m.answer("Сделка не найдена")

    file_id, media_type = extract_file_id_from_message(m)
    if not file_id:
        return await m.answer("Скинь фото/видео/документ")

    await db.set_deal_payment_file(deal_id, file_id)
    await state.clear()
    await m.answer("Чек отправлен на проверку администратору ✅")

    for admin_id in admin_ids:
        try:
            text = (
                f"Новая оплата по сделке #{deal_id}\n"
                f"Покупатель: {deal.buyer_id}\n"
                f"Сумма: {fmt_sum(deal.price)} сум"
            )
            if media_type == "photo":
                await m.bot.send_photo(
                    admin_id,
                    file_id,
                    caption=text,
                    reply_markup=kb_admin_payment_confirm(deal_id),
                )
            elif media_type == "video":
                await m.bot.send_video(
                    admin_id,
                    file_id,
                    caption=text,
                    reply_markup=kb_admin_payment_confirm(deal_id),
                )
            else:
                await m.bot.send_document(
                    admin_id,
                    file_id,
                    caption=text,
                    reply_markup=kb_admin_payment_confirm(deal_id),
                )
        except Exception as e:
            print("RECEIPT ADMIN SEND ERROR:", e)


@user_router.callback_query(F.data.startswith("deal_send_card:"))
async def deal_send_card(cb: CallbackQuery, state: FSMContext, db: DB):
    await safe_cb_answer(cb)
    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")
    if cb.from_user.id != deal.seller_id:
        return await cb.message.answer("Это не твоя сделка")

    await state.update_data(deal_id=deal_id)
    await state.set_state(SellerCard.waiting_card)
    await cb.message.answer("Скинь номер своей карты из 16 цифр. Его увидит только админ.")


@user_router.message(SellerCard.waiting_card)
async def seller_card_input(m: Message, state: FSMContext, db: DB, admin_ids: set[int]):
    card = digits_only(m.text or "")
    if not CARD_RE.match(card):
        return await m.answer("Нужен номер карты из 16 цифр")

    deal_id = int((await state.get_data())["deal_id"])
    deal = await db.get_deal(deal_id)
    if not deal:
        await state.clear()
        return await m.answer("Сделка не найдена")

    await db.set_seller_card(deal_id, card)
    await state.clear()
    await m.answer("Карта отправлена админу ✅")

    for admin_id in admin_ids:
        try:
            await m.bot.send_message(
                admin_id,
                f"Сделка #{deal_id}\nПродавец отправил карту для выплаты:\n{card}\n\nК выплате продавцу: {fmt_sum(deal.seller_payout_amount)} сум"
            )
        except Exception as e:
            print("SELLER CARD ADMIN SEND ERROR:", e)

    try:
        await m.bot.send_message(
            deal.seller_id,
            "Теперь свяжись с покупателем, узнай куда отправить букет, потом отправь букет и скинь доказательство отправки.",
            reply_markup=kb_seller_send_delivery(deal_id)
        )
    except Exception:
        pass


@user_router.callback_query(F.data.startswith("deal_send_delivery:"))
async def deal_send_delivery(cb: CallbackQuery, state: FSMContext, db: DB):
    await safe_cb_answer(cb)
    deal_id = int(cb.data.split(":", 1)[1])
    deal = await db.get_deal(deal_id)
    if not deal:
        return await cb.message.answer("Сделка не найдена")
    if cb.from_user.id != deal.seller_id:
        return await cb.message.answer("Это не твоя сделка")

    if not deal.seller_card:
        return await cb.message.answer("Сначала отправь номер своей карты админу")

    await state.update_data(deal_id=deal_id)
    await state.set_state(SellerDeliveryProof.waiting_proof)
    await cb.message.answer("Скинь фото/видео доказательства отправки или доставки")


@user_router.message(SellerDeliveryProof.waiting_proof)
async def seller_delivery_proof_input(m: Message, state: FSMContext, db: DB, admin_ids: set[int]):
    deal_id = int((await state.get_data())["deal_id"])
    deal = await db.get_deal(deal_id)
    if not deal:
        await state.clear()
        return await m.answer("Сделка не найдена")

    file_id, media_type = extract_file_id_from_message(m)
    if not file_id or media_type not in ("photo", "video"):
        return await m.answer("Скинь фото или видео")

    await db.set_seller_delivery_file(deal_id, file_id)
    await state.clear()
    await m.answer("Доказательство отправлено админу и покупателю ✅")

    try:
        if media_type == "photo":
            await m.bot.send_photo(
                deal.buyer_id,
                file_id,
                caption=(
                    f"Продавец отправил доказательство по сделке #{deal_id}.\n"
                    f"Если букет пришёл — подтверди."
                ),
                reply_markup=kb_buyer_confirm_received(deal_id),
            )
        else:
            await m.bot.send_video(
                deal.buyer_id,
                file_id,
                caption=(
                    f"Продавец отправил доказательство по сделке #{deal_id}.\n"
                    f"Если букет пришёл — подтверди."
                ),
                reply_markup=kb_buyer_confirm_received(deal_id),
            )
    except Exception:
        pass

    for admin_id in admin_ids:
        try:
            if media_type == "photo":
                await m.bot.send_photo(
                    admin_id,
                    file_id,
                    caption=f"Сделка #{deal_id}: продавец отправил доказательство доставки",
                )
            else:
                await m.bot.send_video(
                    admin_id,
                    file_id,
                    caption=f"Сделка #{deal_id}: продавец отправил доказательство доставки",
                )
        except Exception as e:
            print("DELIVERY ADMIN SEND ERROR:", e)
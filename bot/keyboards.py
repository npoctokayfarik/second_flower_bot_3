from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def kb_start() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Я понял(а), хочу разместить", callback_data="new")
    b.button(text="❓ Пример записки", callback_data="example")
    b.adjust(1)
    return b.as_markup()

def kb_confirm() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить на модерацию", callback_data="send_to_review")
    b.button(text="✏️ Изменить заново", callback_data="restart_new")
    b.button(text="❌ Отмена", callback_data="cancel_new")
    b.adjust(1)
    return b.as_markup()

def kb_admin_review(listing_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Опубликовать", callback_data=f"admin_publish:{listing_id}")
    b.button(text="❌ Отклонить", callback_data=f"admin_reject:{listing_id}")
    b.adjust(1)
    return b.as_markup()

def kb_sold(listing_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Продано", callback_data=f"sold:{listing_id}")
    b.adjust(1)
    return b.as_markup()
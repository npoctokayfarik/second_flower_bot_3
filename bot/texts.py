RULES_TEXT = (
    "Правила:\n"
    "• На фото/видео должна быть записка: SECOND FLOWERS\n"
    "• Дата и время — сегодняшние\n"
    "• Записка должна быть видна\n\n"
    "⚠️ Фото из интернета запрещены"
)

AD_FEE = 20000


def fmt_sum(num: int) -> str:
    return f"{num:,}".replace(",", " ")


def build_public_caption(
    title: str,
    region: str,
    city: str,
    district: str,
    address: str,
    freshness: str,
    comment: str,
    price: str,
    phone: str,
    user_username: str | None,
) -> str:
    contact_line = phone.strip()
    if user_username:
        contact_line = f"{contact_line} | @{user_username}"

    loc = f"{region}, {city}"
    if district and district.strip():
        loc += f", {district}"

    return (
        f"<b>{title}</b>\n\n"
        f"Локация: {loc}\n"
        f"Адрес: {address}\n"
        f"Свежесть: {freshness}\n"
        f"Комментарий: {comment}\n\n"
        f"Цена: {price} сум\n"
        f"Контакты: {contact_line}"
    )


def build_admin_info(user_full_name: str, user_username: str | None, user_id: int, phone: str) -> str:
    uname = f"@{user_username}" if user_username else "—"
    return (
        f"От: {user_full_name}\n"
        f"Username: {uname}\n"
        f"ID: {user_id}\n"
        f"Телефон: {phone}"
    )
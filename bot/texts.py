RULES_TEXT = (
    "Перед размещением важно:\n"
    "• На фото и на видео обязательно должна быть записка (листок или экран телефона/планшета/ноутбука) с текстом: SECOND FLOWERS\n"
    "• На фото и видео должна быть одинаковая записка\n"
    "• На записке должна быть сегодняшняя дата и время\n\n"
    "⚠️ Важно:\n"
    "• После публикации фото/видео НЕ удаляются из канала. После успешной продажи удаляются только контакты.\n"
    "• Фото/видео из интернета или канала не принимаются.\n"
    "• Попытки обмана → блок аккаунта.\n\n"
    "Стоимость размещения: 30 000 сум"
)

def build_caption(title: str, region: str, district: str, freshness: str, comment: str, price: str, contact: str) -> str:
    return (
        f"<b>{title}</b>\n\n"
        f"Регион: {region}\n"
        f"Район: {district}\n"
        f"Свежесть: {freshness}\n"
        f"Комментарий: {comment}\n\n"
        f"Цена: {price} сум\n"
        f"Контакты: {contact}"
    )

def mark_sold_caption(caption: str, remove_contacts: bool = True) -> str:
    if remove_contacts:
        lines = caption.splitlines()
        new_lines = []
        for ln in lines:
            if ln.strip().lower().startswith("контакты:"):
                new_lines.append("Контакты: удалены")
            else:
                new_lines.append(ln)
        caption = "\n".join(new_lines)

    if "ПРОДАНО!" in caption:
        return caption
    return caption + "\n\n<b>ПРОДАНО! ✅</b>"
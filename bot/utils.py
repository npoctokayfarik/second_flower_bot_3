from aiogram.types import InputMediaPhoto, InputMediaVideo


def build_media_group(items: list[dict]):
    media = []
    for item in items:
        item_type = item.get("type")
        file_id = item.get("file_id")
        if not file_id:
            continue

        if item_type == "photo":
            media.append(InputMediaPhoto(media=file_id))
        elif item_type == "video":
            media.append(InputMediaVideo(media=file_id))
    return media
from aiogram.types import InputMediaPhoto, InputMediaVideo

def build_media_group(media: list[dict]) -> list:
    items = []
    for m in media:
        if m["type"] == "photo":
            items.append(InputMediaPhoto(media=m["file_id"]))
        else:
            items.append(InputMediaVideo(media=m["file_id"]))
    return items
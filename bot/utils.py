from aiogram.types import InputMediaPhoto, InputMediaVideo


def build_media_group(media_items: list[dict]) -> list:
    group = []
    for item in media_items:
        t = item.get("type")
        fid = item.get("file_id")
        if not fid:
            continue
        if t == "photo":
            group.append(InputMediaPhoto(media=fid))
        elif t == "video":
            group.append(InputMediaVideo(media=fid))
    return group
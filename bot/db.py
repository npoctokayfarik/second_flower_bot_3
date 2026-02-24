import json
import aiosqlite
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Listing:
    id: int
    user_id: int
    status: str
    title: str
    region: str
    district: str
    freshness: str
    comment: str
    price: str
    contact: str
    media_json: str
    caption: str
    channel_first_message_id: Optional[int]
    channel_control_message_id: Optional[int]

class DB:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS listings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              status TEXT NOT NULL,
              title TEXT NOT NULL,
              region TEXT NOT NULL,
              district TEXT NOT NULL,
              freshness TEXT NOT NULL,
              comment TEXT NOT NULL,
              price TEXT NOT NULL,
              contact TEXT NOT NULL,
              media_json TEXT NOT NULL,
              caption TEXT NOT NULL,
              channel_first_message_id INTEGER,
              channel_control_message_id INTEGER
            );
            """)
            await db.commit()

    async def create_listing(self, user_id: int, data: dict[str, Any]) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
              INSERT INTO listings (user_id, status, title, region, district, freshness, comment, price, contact, media_json, caption)
              VALUES (?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data["title"], data["region"], data["district"], data["freshness"],
                data["comment"], data["price"], data["contact"],
                json.dumps(data["media"], ensure_ascii=False),
                data["caption"],
            ))
            await db.commit()
            return cur.lastrowid

    async def get_listing(self, listing_id: int) -> Optional[Listing]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
            row = await cur.fetchone()
            if not row:
                return None
            return Listing(**dict(row))

    async def set_published(self, listing_id: int, first_msg_id: int, control_msg_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
              UPDATE listings
              SET status='published', channel_first_message_id=?, channel_control_message_id=?
              WHERE id=?
            """, (first_msg_id, control_msg_id, listing_id))
            await db.commit()

    async def set_rejected(self, listing_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE listings SET status='rejected' WHERE id=?", (listing_id,))
            await db.commit()

    async def set_sold(self, listing_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE listings SET status='sold' WHERE id=?", (listing_id,))
            await db.commit()

    async def pending_listings(self) -> list[Listing]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM listings WHERE status='pending' ORDER BY id DESC LIMIT 20")
            rows = await cur.fetchall()
            return [Listing(**dict(r)) for r in rows]
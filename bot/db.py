import json
import aiosqlite
from dataclasses import dataclass
from typing import Optional


@dataclass
class Listing:
    id: int
    user_id: int
    user_full_name: str
    user_username: Optional[str]
    status: str
    title: str
    region: str
    city: str
    district: str
    address: str
    freshness: str
    comment: str
    price: str
    contact: str
    media_json: str
    public_caption: str
    channel_first_message_id: Optional[int]
    channel_control_message_id: Optional[int]


@dataclass
class Deal:
    id: int
    listing_id: int
    seller_id: int
    buyer_id: int
    price: int
    commission_amount: int
    seller_payout_amount: int
    seller_card: str = ""
    buyer_payment_file_id: str = ""
    seller_delivery_file_id: str = ""
    status: str = ""
    created_at: str = ""


class DB:
    def __init__(self, path: str):
        self.path = path

    async def _ensure_listings_columns(self, db: aiosqlite.Connection) -> None:
        cur = await db.execute("PRAGMA table_info(listings)")
        rows = await cur.fetchall()
        cols = {row[1] for row in rows}

        if "channel_first_message_id" not in cols:
            await db.execute("ALTER TABLE listings ADD COLUMN channel_first_message_id INTEGER")
        if "channel_control_message_id" not in cols:
            await db.execute("ALTER TABLE listings ADD COLUMN channel_control_message_id INTEGER")
        if "public_caption" not in cols:
            await db.execute("ALTER TABLE listings ADD COLUMN public_caption TEXT NOT NULL DEFAULT ''")

        await db.commit()

    async def _ensure_deals_columns(self, db: aiosqlite.Connection) -> None:
        cur = await db.execute("PRAGMA table_info(deals)")
        rows = await cur.fetchall()
        cols = {row[1] for row in rows}

        if "seller_card" not in cols:
            await db.execute("ALTER TABLE deals ADD COLUMN seller_card TEXT NOT NULL DEFAULT ''")
        if "buyer_payment_file_id" not in cols:
            await db.execute("ALTER TABLE deals ADD COLUMN buyer_payment_file_id TEXT NOT NULL DEFAULT ''")
        if "seller_delivery_file_id" not in cols:
            await db.execute("ALTER TABLE deals ADD COLUMN seller_delivery_file_id TEXT NOT NULL DEFAULT ''")
        if "status" not in cols:
            await db.execute("ALTER TABLE deals ADD COLUMN status TEXT NOT NULL DEFAULT 'waiting_buyer_payment'")

        await db.commit()

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS listings (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              user_full_name TEXT NOT NULL,
              user_username TEXT,
              status TEXT NOT NULL,

              title TEXT NOT NULL,
              region TEXT NOT NULL,
              city TEXT NOT NULL,
              district TEXT NOT NULL,
              address TEXT NOT NULL,

              freshness TEXT NOT NULL,
              comment TEXT NOT NULL,
              price TEXT NOT NULL,
              contact TEXT NOT NULL,

              media_json TEXT NOT NULL,
              public_caption TEXT NOT NULL,

              channel_first_message_id INTEGER,
              channel_control_message_id INTEGER
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS deals (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              listing_id INTEGER NOT NULL,
              seller_id INTEGER NOT NULL,
              buyer_id INTEGER NOT NULL,
              price INTEGER NOT NULL,
              commission_amount INTEGER NOT NULL,
              seller_payout_amount INTEGER NOT NULL,
              seller_card TEXT NOT NULL DEFAULT '',
              buyer_payment_file_id TEXT NOT NULL DEFAULT '',
              seller_delivery_file_id TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            """)

            await self._ensure_listings_columns(db)
            await self._ensure_deals_columns(db)
            await db.commit()

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, value))
            await db.commit()

    async def get_setting(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_examples(self, photo_file_ids: list[str]) -> None:
        await self.set_setting("examples_photo_ids", json.dumps(photo_file_ids, ensure_ascii=False))

    async def get_examples(self) -> list[str]:
        raw = await self.get_setting("examples_photo_ids")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
        return []

    async def create_listing(self, user_id: int, user_full_name: str, user_username: Optional[str], data: dict) -> int:
        district = (data.get("district") or "").strip()

        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
              INSERT INTO listings (
                user_id, user_full_name, user_username, status,
                title, region, city, district, address,
                freshness, comment, price, contact,
                media_json, public_caption, channel_first_message_id, channel_control_message_id
              )
              VALUES (?, ?, ?, 'pending',
                      ?, ?, ?, ?, ?,
                      ?, ?, ?, ?,
                      ?, ?, NULL, NULL)
            """, (
                user_id, user_full_name, user_username,
                data["title"],
                data["region"], data["city"], district, data["address"],
                data["freshness"], data["comment"], str(data["price"]), data["contact"],
                json.dumps(data["media"], ensure_ascii=False),
                data["public_caption"],
            ))
            await db.commit()
            return cur.lastrowid

    async def get_listing(self, listing_id: int) -> Optional[Listing]:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_listings_columns(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM listings WHERE id=?", (listing_id,))
            row = await cur.fetchone()
            return Listing(**dict(row)) if row else None

    async def set_published(self, listing_id: int, first_msg_id: int, control_msg_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_listings_columns(db)
            await db.execute("""
              UPDATE listings
              SET status='published',
                  channel_first_message_id=?,
                  channel_control_message_id=?
              WHERE id=?
            """, (first_msg_id, control_msg_id, listing_id))
            await db.commit()

    async def set_rejected(self, listing_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE listings SET status='rejected' WHERE id=?", (listing_id,))
            await db.commit()

    async def set_listing_reserved(self, listing_id: int, new_public_caption: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
              UPDATE listings
              SET status='reserved', public_caption=?
              WHERE id=?
            """, (new_public_caption, listing_id))
            await db.commit()

    async def set_listing_sold(self, listing_id: int, new_public_caption: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
              UPDATE listings
              SET status='sold', public_caption=?
              WHERE id=?
            """, (new_public_caption, listing_id))
            await db.commit()

    async def create_deal(
        self,
        listing_id: int,
        seller_id: int,
        buyer_id: int,
        price: int,
        commission_amount: int,
        seller_payout_amount: int,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            cur = await db.execute("""
              INSERT INTO deals (
                listing_id, seller_id, buyer_id,
                price, commission_amount, seller_payout_amount,
                status
              )
              VALUES (?, ?, ?, ?, ?, ?, 'waiting_buyer_payment')
            """, (listing_id, seller_id, buyer_id, price, commission_amount, seller_payout_amount))
            await db.commit()
            return cur.lastrowid

    async def get_deal(self, deal_id: int) -> Optional[Deal]:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM deals WHERE id=?", (deal_id,))
            row = await cur.fetchone()
            if not row:
                return None
            data = dict(row)
            return Deal(
                id=data.get("id"),
                listing_id=data.get("listing_id"),
                seller_id=data.get("seller_id"),
                buyer_id=data.get("buyer_id"),
                price=data.get("price"),
                commission_amount=data.get("commission_amount"),
                seller_payout_amount=data.get("seller_payout_amount"),
                seller_card=data.get("seller_card", ""),
                buyer_payment_file_id=data.get("buyer_payment_file_id", ""),
                seller_delivery_file_id=data.get("seller_delivery_file_id", ""),
                status=data.get("status", ""),
                created_at=data.get("created_at", ""),
            )

    async def get_active_deal_by_listing(self, listing_id: int) -> Optional[Deal]:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute("""
              SELECT * FROM deals
              WHERE listing_id=? AND status NOT IN ('cancelled', 'seller_paid')
              ORDER BY id DESC LIMIT 1
            """, (listing_id,))
            row = await cur.fetchone()
            if not row:
                return None
            data = dict(row)
            return Deal(
                id=data.get("id"),
                listing_id=data.get("listing_id"),
                seller_id=data.get("seller_id"),
                buyer_id=data.get("buyer_id"),
                price=data.get("price"),
                commission_amount=data.get("commission_amount"),
                seller_payout_amount=data.get("seller_payout_amount"),
                seller_card=data.get("seller_card", ""),
                buyer_payment_file_id=data.get("buyer_payment_file_id", ""),
                seller_delivery_file_id=data.get("seller_delivery_file_id", ""),
                status=data.get("status", ""),
                created_at=data.get("created_at", ""),
            )

    async def set_deal_payment_file(self, deal_id: int, file_id: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET buyer_payment_file_id=?, status='buyer_paid_pending_admin'
              WHERE id=?
            """, (file_id, deal_id))
            await db.commit()

    async def confirm_buyer_paid(self, deal_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET status='buyer_paid'
              WHERE id=?
            """, (deal_id,))
            await db.commit()

    async def reject_buyer_paid(self, deal_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET status='waiting_buyer_payment', buyer_payment_file_id=''
              WHERE id=?
            """, (deal_id,))
            await db.commit()

    async def set_seller_card(self, deal_id: int, card: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET seller_card=?, status='waiting_seller_delivery'
              WHERE id=?
            """, (card, deal_id))
            await db.commit()

    async def set_seller_delivery_file(self, deal_id: int, file_id: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET seller_delivery_file_id=?, status='waiting_buyer_confirmation'
              WHERE id=?
            """, (file_id, deal_id))
            await db.commit()

    async def set_buyer_confirmed(self, deal_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET status='buyer_confirmed'
              WHERE id=?
            """, (deal_id,))
            await db.commit()

    async def set_problem(self, deal_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET status='problem'
              WHERE id=?
            """, (deal_id,))
            await db.commit()

    async def set_payout_done(self, deal_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await self._ensure_deals_columns(db)
            await db.execute("""
              UPDATE deals
              SET status='seller_paid'
              WHERE id=?
            """, (deal_id,))
            await db.commit()
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _must(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


@dataclass(frozen=True)
class Config:
    bot_token: str
    channel_id: int
    admin_ids: set[int]
    db_path: str
    admin_card: str
    ad_price: int
    port: int


def load_config() -> Config:
    token = _must("BOT_TOKEN")
    channel_id = int(_must("CHANNEL_ID"))
    admin_raw = _must("ADMIN_IDS")
    admin_ids = {int(x.strip()) for x in admin_raw.split(",") if x.strip()}

    db_path = os.getenv("DB_PATH", "second_flowers.sqlite")
    admin_card = os.getenv("ADMIN_CARD", "9860 3501 4697 8852")
    ad_price = int(os.getenv("AD_PRICE", "20000"))
    port = int(os.getenv("PORT", "10000"))

    return Config(
        bot_token=token,
        channel_id=channel_id,
        admin_ids=admin_ids,
        db_path=db_path,
        admin_card=admin_card,
        ad_price=ad_price,
        port=port,
    )
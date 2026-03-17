import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _must(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


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
    return Config(
        bot_token=_must("BOT_TOKEN"),
        channel_id=int(_must("CHANNEL_ID")),
        admin_ids={int(x.strip()) for x in _must("ADMIN_IDS").split(",") if x.strip()},
        db_path=os.getenv("DB_PATH", "second_flowers.sqlite"),
        admin_card=os.getenv("ADMIN_CARD", "9860 3501 4697 8852"),
        ad_price=int(os.getenv("AD_PRICE", "20000")),
        port=int(os.getenv("PORT", "10000")),
    )
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

def load_config() -> Config:
    token = _must("BOT_TOKEN")
    channel_id = int(_must("CHANNEL_ID"))
    admin_raw = _must("ADMIN_IDS")
    admin_ids = {int(x.strip()) for x in admin_raw.split(",") if x.strip()}
    db_path = os.getenv("DB_PATH", "second_flowers.sqlite")
    return Config(
        bot_token=token,
        channel_id=channel_id,
        admin_ids=admin_ids,
        db_path=db_path,
    )
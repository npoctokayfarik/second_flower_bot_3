from aiogram.fsm.state import State, StatesGroup

class NewListing(StatesGroup):
    title = State()
    region = State()
    district = State()
    freshness = State()
    comment = State()
    price = State()
    contact = State()
    media = State()
    confirm = State()
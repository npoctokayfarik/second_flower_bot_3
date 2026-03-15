from aiogram.fsm.state import State, StatesGroup


class NewListing(StatesGroup):
    title = State()
    region = State()
    city = State()
    district = State()
    address = State()
    freshness = State()
    comment = State()
    price = State()
    contact = State()
    media = State()
    confirm = State()


class BuyerDealProof(StatesGroup):
    waiting_proof = State()


class SellerCard(StatesGroup):
    waiting_card = State()


class SellerDeliveryProof(StatesGroup):
    waiting_proof = State()
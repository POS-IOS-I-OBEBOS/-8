from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile
import logging

from .generator import generate_xml

router = Router()
logger = logging.getLogger(__name__)

STATUSES = [
    "New",
    "Cooking",
    "Ready",
    "Delivered",
    "Paid",
    "Closed",
]


class GenStates(StatesGroup):
    status_color = State()
    text_color = State()
    text_size = State()
    panel_bg = State()
    columns = State()
    rows = State()
    blink = State()
    group = State()
    show = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    logger.info("/start by %s", message.from_user.id)
    await state.clear()
    await state.update_data(index=0, statuses={})
    await message.answer(
        "Введите цвет для статуса {} (HEX, например #FF0000):".format(
            STATUSES[0]
        )
    )
    await state.set_state(GenStates.status_color)


@router.message(GenStates.status_color)
async def status_color(message: Message, state: FSMContext):
    logger.info("Status color %s for user %s", message.text.strip(), message.from_user.id)
    data = await state.get_data()
    index = data.get("index", 0)
    statuses = data.get("statuses", {})
    statuses[STATUSES[index]] = message.text.strip()
    index += 1
    if index < len(STATUSES):
        await state.update_data(index=index, statuses=statuses)
        await message.answer(
            f"Введите цвет для статуса {STATUSES[index]} (HEX, например #00FF00):"
        )
        return
    await state.update_data(statuses=statuses)
    await message.answer("Введите цвет текста (например #000000):")
    await state.set_state(GenStates.text_color)


@router.message(GenStates.text_color)
async def text_color(message: Message, state: FSMContext):
    logger.info("Text color %s", message.text.strip())
    await state.update_data(text_color=message.text.strip())
    await message.answer("Введите размер текста (например 12):")
    await state.set_state(GenStates.text_size)


@router.message(GenStates.text_size)
async def text_size(message: Message, state: FSMContext):
    logger.info("Text size %s", message.text.strip())
    await state.update_data(text_size=message.text.strip())
    await message.answer("Введите цвет фона панели (например #FFFFFF):")
    await state.set_state(GenStates.panel_bg)


@router.message(GenStates.panel_bg)
async def panel_bg(message: Message, state: FSMContext):
    logger.info("Panel bg %s", message.text.strip())
    await state.update_data(panel_bg=message.text.strip())
    await message.answer("Введите количество колонок сетки (например 2):")
    await state.set_state(GenStates.columns)


@router.message(GenStates.columns)
async def columns(message: Message, state: FSMContext):
    logger.info("Columns %s", message.text.strip())
    await state.update_data(columns=int(message.text.strip()))
    await message.answer("Введите количество строк сетки (например 3):")
    await state.set_state(GenStates.rows)


@router.message(GenStates.rows)
async def rows(message: Message, state: FSMContext):
    logger.info("Rows %s", message.text.strip())
    await state.update_data(rows=int(message.text.strip()))
    await message.answer("Включить мигание при изменении? (y/n, например y):")
    await state.set_state(GenStates.blink)


@router.message(GenStates.blink)
async def blink(message: Message, state: FSMContext):
    logger.info("Blink %s", message.text.strip())
    await state.update_data(blinkOnChange=message.text.strip().lower().startswith("y"))
    await message.answer("Группировать заказы? (y/n, например n):")
    await state.set_state(GenStates.group)


@router.message(GenStates.group)
async def group(message: Message, state: FSMContext):
    logger.info("Group orders %s", message.text.strip())
    await state.update_data(groupOrders=message.text.strip().lower().startswith("y"))
    await message.answer("Показывать время? (y/n, например y):")
    await state.set_state(GenStates.show)


@router.message(GenStates.show)
async def show(message: Message, state: FSMContext):
    logger.info("Show time %s", message.text.strip())
    await state.update_data(showTime=message.text.strip().lower().startswith("y"))
    data = await state.get_data()
    logger.info("Generating XML for user %s", message.from_user.id)
    path = generate_xml(data)
    logger.info("Sending file %s to user %s", path, message.from_user.id)
    await message.answer_document(FSInputFile(path))
    await message.answer("Готово!")
    await state.clear()

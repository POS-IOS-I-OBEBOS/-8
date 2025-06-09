import logging
import os
import sys
import json
import xml.etree.ElementTree as ET

try:
    from aiogram import Bot, Dispatcher, executor, types
    from aiogram.dispatcher import FSMContext
    from aiogram.dispatcher.filters.state import State, StatesGroup
    from aiogram.contrib.fsm_storage.memory import MemoryStorage
except ModuleNotFoundError as exc:  # pragma: no cover - runtime import check
    print(
        "aiogram is not installed. Please run `pip install -r requirements.txt`"
    )
    raise

# Determine base directory. The script is expected to run directly from
# sources, so we simply use the location of this file.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
XML_PATH = os.path.join(BASE_DIR, "KitchenResources.xml")


def load_token() -> str:
    """Load token from config or environment, prompting the user if needed."""
    # First try the config file
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("BOT_TOKEN")
                if token:
                    return token
        except Exception:
            pass

    # Next, try environment variable
    token = os.getenv("BOT_TOKEN")
    if not token:
        # Ask the user for token interactively on first launch
        token = input("Enter Telegram bot token: ").strip()

    # Save token for future runs
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"BOT_TOKEN": token}, f)
    except Exception as exc:
        logger.error("Failed to save config: %s", exc)

    return token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
TOKEN = load_token()
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# FSM states for editing color
class EditColorFSM(StatesGroup):
    waiting_for_status = State()
    waiting_for_priority = State()
    waiting_for_color = State()


def load_xml() -> ET.ElementTree:
    """Load XML file, creating a default one if it doesn't exist."""
    if not os.path.exists(XML_PATH):
        root = ET.Element("KitchenResources")
        tree = ET.ElementTree(root)
        tree.write(XML_PATH, encoding="utf-8", xml_declaration=True)
    return ET.parse(XML_PATH)


def save_xml(tree: ET.ElementTree):
    tree.write(XML_PATH, encoding="utf-8", xml_declaration=True)


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    load_xml()  # ensure file exists
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("\U0001F3A8 Цвета")
    keyboard.add("\U0001F9F1 Панели")
    keyboard.add("\U0001F520 Шрифты")
    keyboard.add("\U0001F4D0 Сетка")
    await message.answer(
        "Выберите раздел для редактирования:", reply_markup=keyboard
    )


@dp.message_handler(lambda m: m.text == "\U0001F3A8 Цвета")
async def colors_menu(message: types.Message):
    await message.answer("Введите статус блюда (например: CookingStarted):")
    await EditColorFSM.waiting_for_status.set()


@dp.message_handler(state=EditColorFSM.waiting_for_status)
async def color_status(message: types.Message, state: FSMContext):
    await state.update_data(status=message.text.strip())
    await EditColorFSM.next()
    await message.answer("Введите приоритет (Normal или Vip):")


@dp.message_handler(state=EditColorFSM.waiting_for_priority)
async def color_priority(message: types.Message, state: FSMContext):
    await state.update_data(priority=message.text.strip())
    await EditColorFSM.next()
    await message.answer("Введите новый цвет (HEX, например #00FF00):")


@dp.message_handler(state=EditColorFSM.waiting_for_color)
async def color_new(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    status = user_data.get("status")
    priority = user_data.get("priority")
    new_color = message.text.strip()

    tree = load_xml()
    root = tree.getroot()

    style_name = None
    # Search for element with Name=status and attribute like 'NormalStyle' or 'VipStyle'
    attr_name = f"{priority.capitalize()}Style"
    for elem in root.iter():
        if elem.get("Name") == status and attr_name in elem.attrib:
            style_name = elem.attrib[attr_name]
            break

    if not style_name:
        await message.answer("Не удалось найти стиль для указанного статуса и приоритета")
        await state.finish()
        return

    style_elem = None
    for text_style in root.findall("TextStyle"):
        if text_style.get("Name") == style_name:
            style_elem = text_style
            break

    if not style_elem:
        await message.answer("Не найден элемент TextStyle для выбранного стиля")
        await state.finish()
        return

    style_elem.set("FontColor", new_color)
    save_xml(tree)
    await message.answer("Цвет успешно обновлен!")
    await state.finish()


if __name__ == "__main__":  # pragma: no cover - manual run
    executor.start_polling(dp)

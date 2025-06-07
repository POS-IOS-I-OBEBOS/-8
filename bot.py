import json
import logging
import time
import urllib.parse
import urllib.request
import matplotlib

# Use a headless backend so the bot can run without a display and in PyInstaller
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
from pathlib import Path

# These will be populated at startup by asking the user for input
TOKEN = None
API_URL = None

# Telegram user IDs that are allowed to edit groups.
ADMIN_IDS: list[int] = []

# List of group invite links to check. Will be populated at runtime.
required_groups: list[str] = []

# Telegram user IDs that are allowed to edit groups will be
# populated at runtime from user input.

# Files for persistent data
CONFIG_FILE = Path("config.json")
GROUPS_FILE = Path("groups.json")
USERS_FILE = Path("users.json")
EXCLUSIVE_USERS_FILE = Path("exclusive_users.json")

# Invite link provided at startup for exclusive access
INVITE_LINK = ""

# Texts shown to users (loaded from config and editable by admin)
WELCOME_TEXT = "Добро пожаловать! Подпишитесь на наши группы. Используйте кнопки ниже."
BUTTON_VERIFY = "Проверить подписку"
BUTTON_EXCLUSIVE = "Эксклюзив"
BUTTON_LIST = "Список групп"

# Pending admin actions keyed by admin user_id
pending_admin_actions: dict[int, str] = {}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open() as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg))


def load_groups() -> list[str]:
    """Load required group invite links from disk."""
    if GROUPS_FILE.exists():
        try:
            with GROUPS_FILE.open() as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return []
    return []


def save_groups(groups: list[str]):
    GROUPS_FILE.write_text(json.dumps(groups))


def load_users() -> dict:
    """Load saved user info."""
    if USERS_FILE.exists():
        try:
            with USERS_FILE.open() as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return {}
    return {}


def save_users(users: dict):
    USERS_FILE.write_text(json.dumps(users))


def load_exclusive_users() -> list[int]:
    if EXCLUSIVE_USERS_FILE.exists():
        try:
            with EXCLUSIVE_USERS_FILE.open() as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return []
    return []


def save_exclusive_users(data: list[int]):
    EXCLUSIVE_USERS_FILE.write_text(json.dumps(data))


config = load_config()

users = load_users()
exclusive_users = load_exclusive_users()


def record_user(user: dict):
    uid = str(user.get("id"))
    if uid not in users:
        users[uid] = {
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "joined_at": time.time(),
        }
        save_users(users)


def record_exclusive_user(user_id: int):
    if user_id not in exclusive_users:
        exclusive_users.append(user_id)
        save_exclusive_users(exclusive_users)


def configure():
    """Load configuration from disk or ask the user for required data."""
    global TOKEN, API_URL, ADMIN_IDS, required_groups, INVITE_LINK
    global WELCOME_TEXT, BUTTON_VERIFY, BUTTON_EXCLUSIVE, BUTTON_LIST

    logging.info("Loading configuration")
    TOKEN = config.get("token")
    ADMIN_IDS[:] = config.get("admin_ids", [])
    INVITE_LINK = config.get("exclusive_link", "")
    WELCOME_TEXT = config.get("welcome_text", WELCOME_TEXT)
    BUTTON_VERIFY = config.get("button_verify", BUTTON_VERIFY)
    BUTTON_EXCLUSIVE = config.get("button_exclusive", BUTTON_EXCLUSIVE)
    BUTTON_LIST = config.get("button_list", BUTTON_LIST)

    if not TOKEN:
        TOKEN = input("Введите токен Telegram бота: ").strip()
        config["token"] = TOKEN
        logging.info("Token saved")

    if not ADMIN_IDS:
        ids = input("Введите ID администраторов через запятую: ").split(",")
        ADMIN_IDS[:] = [int(i.strip()) for i in ids if i.strip()]
        config["admin_ids"] = ADMIN_IDS
        logging.info("Admin IDs saved")

    required_groups[:] = load_groups()
    if not required_groups:
        groups = input("Пригласительные ссылки на группы через запятую: ").split(",")
        required_groups[:] = [g.strip() for g in groups if g.strip()]
        save_groups(required_groups)
        logging.info("Group links saved")

    if not INVITE_LINK:
        INVITE_LINK = input("Ссылка для эксклюзива: ").strip()
        config["exclusive_link"] = INVITE_LINK
        logging.info("Exclusive link saved")

    save_config(config)
    API_URL = f"https://api.telegram.org/bot{TOKEN}/"
    logging.info("Configuration complete")




def is_admin(user_id: int) -> bool:
    """Check whether a user is allowed to manage groups."""
    return user_id in ADMIN_IDS

ACCESS_GRANTED_MSG = "Подписка подтверждена. Доступ открыт!"
ACCESS_DENIED_MSG = (
    "Вы еще не подписались на все требуемые группы. Пожалуйста, проверьте "
    "свои подписки и попробуйте снова."
)
EXCLUSIVE_CONTENT = "Эксклюзивная ссылка: {link}"

ADMIN_KEYBOARD = {
    "keyboard": [
        ["Список групп", "Добавить группу", "Удалить группу"],
        ["Изменить приветствие", "Изменить кнопки"],
        ["Статистика", "Подробная статистика", "Пользователи"],
    ],
    "resize_keyboard": True,
}


def call_api(method: str, params: dict | None = None) -> dict:
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(API_URL + method, data=data)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.load(response)
            logging.debug("API %s -> %s", method, result)
            return result
    except Exception as e:  # pragma: no cover - log API errors
        logging.error("API call failed: %s", e)
        return {}


def get_updates(offset: int | None = None) -> list[dict]:
    params = {"timeout": 100}
    if offset:
        params["offset"] = offset
    resp = call_api("getUpdates", params)
    return resp.get("result", [])


def send_message(chat_id: int, text: str, reply_markup: dict | None = None):
    params = {"chat_id": chat_id, "text": text}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    logging.debug("Send message to %s: %s", chat_id, text)
    call_api("sendMessage", params)


def send_photo(chat_id: int, photo_path: str, caption: str | None = None):
    boundary = f"----WebKitFormBoundary{int(time.time())}"
    lines = []
    lines.extend([
        f"--{boundary}",
        'Content-Disposition: form-data; name="chat_id"',
        "",
        str(chat_id),
    ])
    if caption:
        lines.extend([
            f"--{boundary}",
            'Content-Disposition: form-data; name="caption"',
            "",
            caption,
        ])
    lines.extend([
        f"--{boundary}",
        'Content-Disposition: form-data; name="photo"; filename="stats.jpg"',
        'Content-Type: image/jpeg',
        "",
    ])
    with open(photo_path, "rb") as f:
        body = "\r\n".join(lines).encode() + f.read() + f"\r\n--{boundary}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    logging.debug("Send photo to %s: %s", chat_id, photo_path)
    req = urllib.request.Request(API_URL + "sendPhoto", data=body, headers=headers)
    urllib.request.urlopen(req).read()


def generate_stats_graph(path: str) -> bool:
    """Generate a visits graph and save to given path. Return False if no data."""
    counts: dict[str, int] = {}
    for u in users.values():
        ts = u.get("joined_at")
        if not ts:
            continue
        day = time.strftime("%Y-%m-%d", time.localtime(ts))
        counts[day] = counts.get(day, 0) + 1
    if not counts:
        return False
    logging.info("Generating statistics graph with %d points", len(counts))
    dates = sorted(counts)
    values = [counts[d] for d in dates]
    plt.figure()
    plt.plot(dates, values, marker="o")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    logging.info("User %s subscribed to all groups", user_id)
    return True


def check_subscriptions(user_id: int) -> bool:
    """Return True if user is a member of all required groups."""
    logging.info("Checking subscriptions for user %s", user_id)
    for link in required_groups:
        member = call_api(
            "getChatMember", {"chat_id": link, "user_id": user_id}
        )
        status = member.get("result", {}).get("status")
        if status in {"left", "kicked"} or status is None:
            logging.info("User %s missing subscription to %s", user_id, link)
            return False
    return True


def handle_callback_query(query: dict):
    query_id = query["id"]
    data = query.get("data")
    user_id = query["from"]["id"]
    chat_id = query["message"]["chat"]["id"]

    if data == "list_groups":
        if required_groups:
            keyboard = {
                "inline_keyboard": [
                    [{"text": f"Группа {i+1}", "url": link}]
                    for i, link in enumerate(required_groups)
                ]
            }
            send_message(chat_id, "Необходимые группы:", keyboard)
        else:
            send_message(chat_id, "Список групп пуст")
    elif data == "verify":
        if check_subscriptions(user_id):
            send_message(chat_id, ACCESS_GRANTED_MSG)
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif data == "exclusive":
        if check_subscriptions(user_id):
            record_exclusive_user(user_id)
            send_message(chat_id, EXCLUSIVE_CONTENT.format(link=INVITE_LINK))
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    call_api("answerCallbackQuery", {"callback_query_id": query_id})


def handle_update(update: dict):
    if "callback_query" in update:
        handle_callback_query(update["callback_query"])
        return
    message = update.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    logging.info("Message from %s: %s", user_id, text)

    record_user(message.get("from", {}))

    if is_admin(user_id) and user_id in pending_admin_actions:
        action = pending_admin_actions.pop(user_id)
        payload = text.strip()
        if action == "add":
            if payload and payload not in required_groups:
                required_groups.append(payload)
                save_groups(required_groups)
            logging.info("Admin %s added group %s", user_id, payload)
            send_message(chat_id, "Группа добавлена")
        elif action == "remove":
            if payload in required_groups:
                required_groups.remove(payload)
                save_groups(required_groups)
            logging.info("Admin %s removed group %s", user_id, payload)
            send_message(chat_id, "Группа удалена")
        elif action == "welcome":
            if payload:
                global WELCOME_TEXT
                WELCOME_TEXT = payload
                config["welcome_text"] = WELCOME_TEXT
                save_config(config)
                logging.info("Admin %s updated welcome text", user_id)
                send_message(chat_id, "Приветствие обновлено")
        elif action == "buttons":
            parts = [p.strip() for p in payload.split(",")]
            if len(parts) == 3:
                global BUTTON_LIST, BUTTON_VERIFY, BUTTON_EXCLUSIVE
                BUTTON_LIST, BUTTON_VERIFY, BUTTON_EXCLUSIVE = parts
                config["button_list"] = BUTTON_LIST
                config["button_verify"] = BUTTON_VERIFY
                config["button_exclusive"] = BUTTON_EXCLUSIVE
                save_config(config)
                logging.info("Admin %s updated button labels", user_id)
                send_message(chat_id, "Кнопки обновлены")
            else:
                send_message(chat_id, "Неверный формат. Три названия через запятую")
        return

    if text.startswith("/start"):
        logging.info("/start command from %s", user_id)
        group_buttons = [
            [{"text": f"Группа {i+1}", "url": link}]
            for i, link in enumerate(required_groups)
        ]
        keyboard = {
            "inline_keyboard": group_buttons
            + [
                [{"text": BUTTON_LIST, "callback_data": "list_groups"}],
                [{"text": BUTTON_VERIFY, "callback_data": "verify"}],
                [{"text": BUTTON_EXCLUSIVE, "callback_data": "exclusive"}],
            ]
        }
        send_message(chat_id, WELCOME_TEXT, keyboard)
    elif text.startswith("/verify"):
        logging.info("/verify command from %s", user_id)
        if check_subscriptions(user_id):
            send_message(chat_id, ACCESS_GRANTED_MSG)
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif text.startswith("/listgroups"):
        logging.info("/listgroups command from %s", user_id)
        if required_groups:
            keyboard = {
                "inline_keyboard": [
                    [{"text": f"Группа {i+1}", "url": link}]
                    for i, link in enumerate(required_groups)
                ]
            }
            send_message(chat_id, "Необходимые группы:", keyboard)
        else:
            send_message(chat_id, "Список групп пуст")
    elif text.startswith("/exclusive"):
        logging.info("/exclusive command from %s", user_id)
        if check_subscriptions(user_id):
            record_exclusive_user(user_id)
            send_message(chat_id, EXCLUSIVE_CONTENT.format(link=INVITE_LINK))
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif text.startswith("/admin"):
        logging.info("/admin command from %s", user_id)
        if is_admin(user_id):
            send_message(chat_id, "Панель администратора", ADMIN_KEYBOARD)
        else:
            send_message(chat_id, "Нет доступа")
    elif is_admin(user_id) and text == "Список групп":
        groups_text = "\n".join(required_groups) or "нет"
        send_message(chat_id, f"Текущие группы:\n{groups_text}")
    elif is_admin(user_id) and text == "Добавить группу":
        pending_admin_actions[user_id] = "add"
        send_message(chat_id, "Отправьте ссылку на группу")
    elif is_admin(user_id) and text == "Удалить группу":
        pending_admin_actions[user_id] = "remove"
        send_message(chat_id, "Отправьте ссылку на группу для удаления")
    elif is_admin(user_id) and text == "Статистика":
        send_message(chat_id, f"Пользователей: {len(users)}")
    elif is_admin(user_id) and text == "Пользователи":
        info = [f"{uid} - {u.get('username') or u.get('first_name')}" for uid, u in users.items()]
        send_message(chat_id, "\n".join(info) or "Нет данных")
    elif is_admin(user_id) and text == "Изменить приветствие":
        pending_admin_actions[user_id] = "welcome"
        send_message(chat_id, "Отправьте новый приветственный текст")
    elif is_admin(user_id) and text == "Изменить кнопки":
        pending_admin_actions[user_id] = "buttons"
        send_message(chat_id, "Названия кнопок через запятую: список, проверка, эксклюзив")
    elif is_admin(user_id) and text == "Подробная статистика":
        logging.info("Generating detailed stats for admin %s", user_id)
        if generate_stats_graph("stats.jpg"):
            send_photo(chat_id, "stats.jpg")
        else:
            send_message(chat_id, "Нет данных")
    elif text.startswith("/groups"):
        logging.info("/groups command from %s", user_id)
        if is_admin(user_id):
            groups_text = "\n".join(required_groups) or "нет"
            send_message(chat_id, f"Текущие группы:\n{groups_text}")
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/addgroup"):
        logging.info("/addgroup command from %s", user_id)
        if is_admin(user_id):
            try:
                link = text.split(maxsplit=1)[1].strip()
                if link and link not in required_groups:
                    required_groups.append(link)
                    save_groups(required_groups)
                send_message(chat_id, "Группа добавлена")
            except IndexError:
                send_message(chat_id, "Использование: /addgroup <link>")
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/removegroup"):
        logging.info("/removegroup command from %s", user_id)
        if is_admin(user_id):
            try:
                link = text.split(maxsplit=1)[1].strip()
                if link in required_groups:
                    required_groups.remove(link)
                    save_groups(required_groups)
                send_message(chat_id, "Группа удалена")
            except IndexError:
                send_message(chat_id, "Использование: /removegroup <link>")
        else:
            send_message(chat_id, "Нет доступа")


if __name__ == "__main__":
    logging.info("Bot starting")
    configure()
    offset = None
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            try:
                handle_update(upd)
            except Exception as e:  # pragma: no cover - log the error
                logging.exception("Error handling update: %s", e)
        time.sleep(1)

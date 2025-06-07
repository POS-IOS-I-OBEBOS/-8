import json
import time
import urllib.parse
import urllib.request
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
        }
        save_users(users)


def record_exclusive_user(user_id: int):
    if user_id not in exclusive_users:
        exclusive_users.append(user_id)
        save_exclusive_users(exclusive_users)


def configure():
    """Load configuration from disk or ask the user for required data."""
    global TOKEN, API_URL, ADMIN_IDS, required_groups, INVITE_LINK

    TOKEN = config.get("token")
    ADMIN_IDS[:] = config.get("admin_ids", [])
    INVITE_LINK = config.get("exclusive_link", "")

    if not TOKEN:
        TOKEN = input("Введите токен Telegram бота: ").strip()
        config["token"] = TOKEN

    if not ADMIN_IDS:
        ids = input("Введите ID администраторов через запятую: ").split(",")
        ADMIN_IDS[:] = [int(i.strip()) for i in ids if i.strip()]
        config["admin_ids"] = ADMIN_IDS

    required_groups[:] = load_groups()
    if not required_groups:
        groups = input("Пригласительные ссылки на группы через запятую: ").split(",")
        required_groups[:] = [g.strip() for g in groups if g.strip()]
        save_groups(required_groups)

    if not INVITE_LINK:
        INVITE_LINK = input("Ссылка для эксклюзива: ").strip()
        config["exclusive_link"] = INVITE_LINK

    save_config(config)
    API_URL = f"https://api.telegram.org/bot{TOKEN}/"




def is_admin(user_id: int) -> bool:
    """Check whether a user is allowed to manage groups."""
    return user_id in ADMIN_IDS

WELCOME_MSG = (
    "Добро пожаловать! Подпишитесь на наши группы. "
    "Используйте кнопки ниже, чтобы проверить подписку или получить доступ."
)
ACCESS_GRANTED_MSG = "Подписка подтверждена. Доступ открыт!"
ACCESS_DENIED_MSG = (
    "Вы еще не подписались на все требуемые группы. Пожалуйста, проверьте "
    "свои подписки и попробуйте снова."
)
EXCLUSIVE_CONTENT = "Эксклюзивная ссылка: {link}"

ADMIN_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "Список групп", "callback_data": "admin_list"}],
        [{"text": "Добавить группу", "callback_data": "admin_add"}],
        [{"text": "Удалить группу", "callback_data": "admin_remove"}],
        [{"text": "Статистика", "callback_data": "admin_stats"}],
        [{"text": "Пользователи", "callback_data": "admin_users"}],
    ]
}


def call_api(method: str, params: dict | None = None) -> dict:
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(API_URL + method, data=data)
    with urllib.request.urlopen(req) as response:
        return json.load(response)


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
    call_api("sendMessage", params)


def check_subscriptions(user_id: int) -> bool:
    """Return True if user is a member of all required groups."""
    for link in required_groups:
        member = call_api(
            "getChatMember", {"chat_id": link, "user_id": user_id}
        )
        status = member.get("result", {}).get("status")
        if status in {"left", "kicked"} or status is None:
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
    elif data == "admin_list" and is_admin(user_id):
        groups_text = "\n".join(required_groups) or "нет"
        send_message(chat_id, f"Текущие группы:\n{groups_text}")
    elif data == "admin_add" and is_admin(user_id):
        pending_admin_actions[user_id] = "add"
        send_message(chat_id, "Отправьте ссылку на группу для добавления")
    elif data == "admin_remove" and is_admin(user_id):
        pending_admin_actions[user_id] = "remove"
        send_message(chat_id, "Отправьте ссылку на группу для удаления")
    elif data == "admin_stats" and is_admin(user_id):
        send_message(chat_id, f"Пользователей: {len(users)}")
    elif data == "admin_users" and is_admin(user_id):
        info = [f"{uid} - {u.get('username') or u.get('first_name')}" for uid, u in users.items()]
        send_message(chat_id, "\n".join(info) or "Нет данных")
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

    record_user(message.get("from", {}))

    if is_admin(user_id) and user_id in pending_admin_actions:
        action = pending_admin_actions.pop(user_id)
        link = text.strip()
        if not link:
            send_message(chat_id, "Неверная ссылка")
            return
        if action == "add":
            if link not in required_groups:
                required_groups.append(link)
                save_groups(required_groups)
            send_message(chat_id, "Группа добавлена")
        else:
            if link in required_groups:
                required_groups.remove(link)
                save_groups(required_groups)
            send_message(chat_id, "Группа удалена")
        return

    if text.startswith("/start"):
        group_buttons = [
            [{"text": f"Группа {i+1}", "url": link}]
            for i, link in enumerate(required_groups)
        ]
        keyboard = {
            "inline_keyboard": group_buttons
            + [
                [{"text": "Проверить подписку", "callback_data": "verify"}],
                [{"text": "Эксклюзив", "callback_data": "exclusive"}],
            ]
        }
        send_message(chat_id, WELCOME_MSG, keyboard)
    elif text.startswith("/verify"):
        if check_subscriptions(user_id):
            send_message(chat_id, ACCESS_GRANTED_MSG)
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif text.startswith("/listgroups"):
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
        if check_subscriptions(user_id):
            record_exclusive_user(user_id)
            send_message(chat_id, EXCLUSIVE_CONTENT.format(link=INVITE_LINK))
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif text.startswith("/admin"):
        if is_admin(user_id):
            send_message(chat_id, "Панель администратора", ADMIN_KEYBOARD)
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/groups"):
        if is_admin(user_id):
            groups_text = "\n".join(required_groups) or "нет"
            send_message(chat_id, f"Текущие группы:\n{groups_text}")
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/addgroup"):
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
    configure()
    offset = None
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            try:
                handle_update(upd)
            except Exception as e:  # pragma: no cover - log the error
                print("Error handling update", e)
        time.sleep(1)

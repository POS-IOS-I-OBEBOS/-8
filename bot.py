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

# List of group or channel IDs to check. Will be populated at runtime.
required_groups: list[int] = []

# Telegram user IDs that are allowed to edit groups will be
# populated at runtime from user input.

# Files for persistent data
GROUPS_FILE = Path("groups.json")
USERS_FILE = Path("users.json")

# Invite link provided at startup for exclusive access
INVITE_LINK = ""

# Pending admin actions keyed by admin user_id
pending_admin_actions: dict[int, str] = {}


def load_groups() -> list[int]:
    """Load required groups from disk."""
    if GROUPS_FILE.exists():
        try:
            with GROUPS_FILE.open() as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return []
    return []


def save_groups(groups: list[int]):
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


users = load_users()


def record_user(user: dict):
    uid = str(user.get("id"))
    if uid not in users:
        users[uid] = {
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
        }
        save_users(users)


def configure():
    """Ask the user for the bot token, admins, groups and invite link."""
    global TOKEN, API_URL, ADMIN_IDS, required_groups, INVITE_LINK
    if not TOKEN:
        TOKEN = input("Введите токен Telegram бота: ").strip()
    if not ADMIN_IDS:
        ids = input("Введите ID администраторов через запятую: ").split(",")
        ADMIN_IDS = [int(i.strip()) for i in ids if i.strip()]
    groups = input("Введите ID каналов через запятую: ").split(",")
    required_groups = [int(g.strip()) for g in groups if g.strip()]
    save_groups(required_groups)
    INVITE_LINK = input("Ссылка для эксклюзива: ").strip()
    API_URL = f"https://api.telegram.org/bot{TOKEN}/"




def is_admin(user_id: int) -> bool:
    """Check whether a user is allowed to manage groups."""
    return user_id in ADMIN_IDS

WELCOME_MSG = (
    "Добро пожаловать! Подпишитесь на наши каналы и группы. "
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
        [{"text": "Список каналов", "callback_data": "admin_list"}],
        [{"text": "Добавить канал", "callback_data": "admin_add"}],
        [{"text": "Удалить канал", "callback_data": "admin_remove"}],
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
    for group_id in required_groups:
        member = call_api(
            "getChatMember", {"chat_id": group_id, "user_id": user_id}
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
        groups_text = "\n".join(map(str, required_groups)) or "нет"
        send_message(chat_id, f"Необходимые группы:\n{groups_text}")
    elif data == "verify":
        if check_subscriptions(user_id):
            send_message(chat_id, ACCESS_GRANTED_MSG)
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif data == "exclusive":
        if check_subscriptions(user_id):
            send_message(chat_id, EXCLUSIVE_CONTENT.format(link=INVITE_LINK))
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif data == "admin_list" and is_admin(user_id):
        groups_text = "\n".join(map(str, required_groups)) or "нет"
        send_message(chat_id, f"Текущие группы:\n{groups_text}")
    elif data == "admin_add" and is_admin(user_id):
        pending_admin_actions[user_id] = "add"
        send_message(chat_id, "Отправьте ID канала для добавления")
    elif data == "admin_remove" and is_admin(user_id):
        pending_admin_actions[user_id] = "remove"
        send_message(chat_id, "Отправьте ID канала для удаления")
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
        try:
            group_id = int(text)
        except ValueError:
            send_message(chat_id, "Неверный ID")
            return
        if action == "add":
            if group_id not in required_groups:
                required_groups.append(group_id)
                save_groups(required_groups)
            send_message(chat_id, "Группа добавлена")
        else:
            if group_id in required_groups:
                required_groups.remove(group_id)
                save_groups(required_groups)
            send_message(chat_id, "Группа удалена")
        return

    if text.startswith("/start"):
        keyboard = {
            "inline_keyboard": [
                [{"text": "Список групп", "callback_data": "list_groups"}],
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
        groups_text = "\n".join(map(str, required_groups)) or "нет"
        send_message(chat_id, f"Необходимые группы:\n{groups_text}")
    elif text.startswith("/exclusive"):
        if check_subscriptions(user_id):
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
            groups_text = "\n".join(map(str, required_groups)) or "нет"
            send_message(chat_id, f"Текущие группы:\n{groups_text}")
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/addgroup"):
        if is_admin(user_id):
            try:
                group_id = int(text.split(maxsplit=1)[1])
                if group_id not in required_groups:
                    required_groups.append(group_id)
                    save_groups(required_groups)
                send_message(chat_id, "Группа добавлена")
            except (IndexError, ValueError):
                send_message(chat_id, "Использование: /addgroup <id>")
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/removegroup"):
        if is_admin(user_id):
            try:
                group_id = int(text.split(maxsplit=1)[1])
                if group_id in required_groups:
                    required_groups.remove(group_id)
                    save_groups(required_groups)
                send_message(chat_id, "Группа удалена")
            except (IndexError, ValueError):
                send_message(chat_id, "Использование: /removegroup <id>")
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

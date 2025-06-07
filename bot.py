import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
API_URL = f"https://api.telegram.org/bot{TOKEN}/"

# List of group or channel IDs the user must be subscribed to by default
REQUIRED_GROUPS = [
    -1001234567890,  # replace with your group IDs
    -1009876543210,
]

# Telegram user IDs that are allowed to edit groups
ADMIN_IDS = [123456789]

# File where group IDs are stored so that admins can edit them
GROUPS_FILE = Path("groups.json")


def load_groups() -> list[int]:
    """Load required groups from disk or create the file with defaults."""
    if GROUPS_FILE.exists():
        try:
            with GROUPS_FILE.open() as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            pass
    GROUPS_FILE.write_text(json.dumps(REQUIRED_GROUPS))
    return REQUIRED_GROUPS


def save_groups(groups: list[int]):
    GROUPS_FILE.write_text(json.dumps(groups))


required_groups = load_groups()


def is_admin(user_id: int) -> bool:
    """Check whether a user is allowed to manage groups."""
    return user_id in ADMIN_IDS

WELCOME_MSG = (
    "Добро пожаловать! Подпишитесь на все наши каналы и группы, затем "
    "отправьте команду /verify для проверки подписки."
)
ACCESS_GRANTED_MSG = "Подписка подтверждена. Доступ открыт!"
ACCESS_DENIED_MSG = (
    "Вы еще не подписались на все требуемые группы. Пожалуйста, проверьте "
    "свои подписки и попробуйте снова."
)


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


def send_message(chat_id: int, text: str):
    call_api("sendMessage", {"chat_id": chat_id, "text": text})


def check_subscriptions(user_id: int) -> bool:
    for group_id in required_groups:
        member = call_api(
            "getChatMember", {"chat_id": group_id, "user_id": user_id}
        )
        status = member.get("result", {}).get("status")
        if status in {"left", "kicked"} or status is None:
            return False
    return True


def handle_update(update: dict):
    message = update.get("message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    if text.startswith("/start"):
        send_message(chat_id, WELCOME_MSG)
    elif text.startswith("/verify"):
        if check_subscriptions(user_id):
            send_message(chat_id, ACCESS_GRANTED_MSG)
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif text.startswith("/admin"):
        if is_admin(user_id):
            send_message(
                chat_id,
                "Команды: /groups, /addgroup <id>, /removegroup <id>",
            )
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

import json
import logging
import time
import urllib.parse
import urllib.request
import matplotlib

# Use a headless backend so the bot can run without a display and in PyInstaller
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import threading
import tkinter as tk
from tkinter import scrolledtext

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

# List of groups to check. Each entry is a dict with "id" and "link" keys
# containing the chat ID (or @username) for subscription verification and the
# invite link users should follow.
required_groups: list[dict] = []

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


class TkLogHandler(logging.Handler):
    """Logging handler that writes messages to a Tkinter Text widget."""

    def __init__(self, widget: tk.Text):
        super().__init__()
        self.widget = widget
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)

        def append():
            self.widget.configure(state="normal")
            self.widget.insert(tk.END, msg + "\n")
            self.widget.configure(state="disabled")
            self.widget.yview(tk.END)

        self.widget.after(0, append)


def start_log_window() -> tk.Tk:
    """Create a window that displays log messages and return it."""

    window = tk.Tk()
    window.title("Логи бота")
    text = scrolledtext.ScrolledText(window, width=80, height=20, state="disabled")
    text.pack(expand=True, fill="both")
    handler = TkLogHandler(text)
    logging.getLogger().addHandler(handler)
    return window


def configure_gui():
    """Show a configuration window and save results to files."""
    global TOKEN, ADMIN_IDS, INVITE_LINK, required_groups

    root = tk.Tk()
    root.title("Настройка бота")

    tk.Label(root, text="Токен (пример: 123456789:ABCDEF)").grid(row=0, column=0, sticky="w")
    ent_token = tk.Entry(root, width=50)
    ent_token.insert(0, config.get("token", ""))
    ent_token.grid(row=0, column=1)

    tk.Label(root, text="ID админов через запятую (пример: 12345,67890)").grid(row=1, column=0, sticky="w")
    ent_admins = tk.Entry(root, width=50)
    ent_admins.insert(0, ",".join(str(i) for i in config.get("admin_ids", [])))
    ent_admins.grid(row=1, column=1)

    tk.Label(root, text="ID каналов через запятую (пример: -100123,@channel)").grid(row=2, column=0, sticky="w")
    ent_group_ids = tk.Entry(root, width=50)
    ent_group_ids.insert(0, ",".join(g.get("id", "") for g in load_groups()))
    ent_group_ids.grid(row=2, column=1)

    tk.Label(root, text="Ссылки на каналы через запятую").grid(row=3, column=0, sticky="w")
    ent_group_links = tk.Entry(root, width=50)
    ent_group_links.insert(0, ",".join(g.get("link", "") for g in load_groups()))
    ent_group_links.grid(row=3, column=1)

    tk.Label(root, text="Эксклюзивная ссылка (пример: https://t.me/joinchat/xxxx)").grid(row=4, column=0, sticky="w")
    ent_invite = tk.Entry(root, width=50)
    ent_invite.insert(0, config.get("exclusive_link", ""))
    ent_invite.grid(row=4, column=1)

    def on_start():
        nonlocal root
        TOKEN = ent_token.get().strip()
        ADMIN_IDS[:] = [int(i.strip()) for i in ent_admins.get().split(",") if i.strip()]
        ids = [g.strip() for g in ent_group_ids.get().split(",") if g.strip()]
        links = [g.strip() for g in ent_group_links.get().split(",") if g.strip()]
        required_groups[:] = [
            {"id": ids[i], "link": links[i] if i < len(links) else ""}
            for i in range(len(ids))
        ]
        INVITE_LINK = ent_invite.get().strip()

        config["token"] = TOKEN
        config["admin_ids"] = ADMIN_IDS
        config["exclusive_link"] = INVITE_LINK
        save_config(config)
        save_groups(required_groups)
        root.destroy()

    tk.Button(root, text="Запустить", command=on_start).grid(row=5, column=0, columnspan=2, pady=5)
    root.mainloop()


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


def load_groups() -> list[dict]:
    """Load required groups from disk."""
    if GROUPS_FILE.exists():
        try:
            with GROUPS_FILE.open() as fh:
                data = json.load(fh)
            if isinstance(data, list):
                groups = []
                for item in data:
                    if isinstance(item, dict):
                        groups.append({"id": item.get("id", ""), "link": item.get("link", "")})
                    else:
                        groups.append({"id": item, "link": item})
                return groups
        except json.JSONDecodeError:
            return []
    return []


def save_groups(groups: list[dict]):
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
    """Load configuration from disk and open the GUI to edit it."""
    global TOKEN, API_URL, ADMIN_IDS, required_groups, INVITE_LINK
    global WELCOME_TEXT, BUTTON_VERIFY, BUTTON_EXCLUSIVE, BUTTON_LIST

    logging.info("Loading configuration")
    TOKEN = config.get("token", "")
    ADMIN_IDS[:] = config.get("admin_ids", [])
    INVITE_LINK = config.get("exclusive_link", "")
    WELCOME_TEXT = config.get("welcome_text", WELCOME_TEXT)
    BUTTON_VERIFY = config.get("button_verify", BUTTON_VERIFY)
    BUTTON_EXCLUSIVE = config.get("button_exclusive", BUTTON_EXCLUSIVE)
    BUTTON_LIST = config.get("button_list", BUTTON_LIST)
    required_groups[:] = load_groups()

    configure_gui()

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
        logging.error("API call failed: %s. Проверьте токен и интернет.", e)
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
    return True


def check_subscriptions(user_id: int) -> bool:
    """Return True if user is a member of all required groups."""
    logging.info("Checking subscriptions for user %s", user_id)
    for grp in required_groups:
        chat_id = grp.get("id")
        member = call_api(
            "getChatMember", {"chat_id": chat_id, "user_id": user_id}
        )
        status = member.get("result", {}).get("status")
        if status in {"left", "kicked"} or status is None:
            logging.info("User %s missing subscription to %s", user_id, chat_id)
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
                    [{"text": f"Группа {i+1}", "url": grp.get("link") or str(grp.get("id"))}]
                    for i, grp in enumerate(required_groups)
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
            try:
                gid, link = payload.split(maxsplit=1)
                if all(g.get("id") != gid for g in required_groups):
                    required_groups.append({"id": gid, "link": link})
                    save_groups(required_groups)
                logging.info("Admin %s added group %s", user_id, gid)
                send_message(chat_id, "Группа добавлена")
            except Exception:
                send_message(chat_id, "Нужно отправить: <id> <link>")
        elif action == "remove":
            idx = next((i for i, g in enumerate(required_groups) if g.get("id") == payload), None)
            if idx is not None:
                required_groups.pop(idx)
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
            [{"text": f"Группа {i+1}", "url": grp.get("link") or str(grp.get("id"))}]
            for i, grp in enumerate(required_groups)
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
                    [{"text": f"Группа {i+1}", "url": grp.get("link") or str(grp.get("id"))}]
                    for i, grp in enumerate(required_groups)
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
        groups_text = "\n".join(f"{g.get('id')} -> {g.get('link')}" for g in required_groups) or "нет"
        send_message(chat_id, f"Текущие группы:\n{groups_text}")
    elif is_admin(user_id) and text == "Добавить группу":
        pending_admin_actions[user_id] = "add"
        send_message(chat_id, "Отправьте: <id> <ссылка>")
    elif is_admin(user_id) and text == "Удалить группу":
        pending_admin_actions[user_id] = "remove"
        send_message(chat_id, "Отправьте ID группы для удаления")
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
            groups_text = "\n".join(f"{g.get('id')} -> {g.get('link')}" for g in required_groups) or "нет"
            send_message(chat_id, f"Текущие группы:\n{groups_text}")
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/addgroup"):
        logging.info("/addgroup command from %s", user_id)
        if is_admin(user_id):
            try:
                _, params = text.split(maxsplit=1)
                gid, link = params.split(maxsplit=1)
                grp = {"id": gid.strip(), "link": link.strip()}
                if all(g.get("id") != gid for g in required_groups):
                    required_groups.append(grp)
                    save_groups(required_groups)
                send_message(chat_id, "Группа добавлена")
            except Exception:
                send_message(chat_id, "Использование: /addgroup <id> <link>")
        else:
            send_message(chat_id, "Нет доступа")
    elif text.startswith("/removegroup"):
        logging.info("/removegroup command from %s", user_id)
        if is_admin(user_id):
            try:
                gid = text.split(maxsplit=1)[1].strip()
                idx = next(
                    (i for i, g in enumerate(required_groups) if g.get("id") == gid),
                    None,
                )
                if idx is not None:
                    required_groups.pop(idx)
                    save_groups(required_groups)
                send_message(chat_id, "Группа удалена")
            except IndexError:
                send_message(chat_id, "Использование: /removegroup <id>")
        else:
            send_message(chat_id, "Нет доступа")


def run_bot():
    """Main loop for polling updates."""
    offset = None
    while True:
        updates = get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            try:
                handle_update(upd)
            except Exception as e:  # pragma: no cover - log the error
                logging.exception(
                    "Ошибка обработки обновления. Проверьте настройки и интернет-соединение: %s",
                    e,
                )
        time.sleep(1)


if __name__ == "__main__":
    logging.info("Bot starting")
    configure()
    log_window = start_log_window()
    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
    log_window.mainloop()

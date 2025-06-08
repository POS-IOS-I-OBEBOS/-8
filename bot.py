import json
import logging
import time
import urllib.parse
import urllib.request
import ssl
import re
import html
import matplotlib
from pathlib import Path
import io
import tempfile
from tkinter import scrolledtext, messagebox
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    PIL_AVAILABLE = False
try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    PSUTIL_AVAILABLE = False

# Use a headless backend so the bot can run without a display and in PyInstaller
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import threading
import tkinter as tk

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

FSRAR_LOG = Path("fsrar.log")
fsrar_logger = logging.getLogger("fsrar")
fsrar_logger.setLevel(logging.INFO)
_fh = logging.FileHandler(FSRAR_LOG, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
fsrar_logger.addHandler(_fh)

UNVERIFIED_CONTEXT = ssl._create_unverified_context()

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
AUTHORIZED_USERS_FILE = Path("authorized_users.json")

# Texts shown to users (loaded from config and editable by admin)
WELCOME_TEXT = "Добро пожаловать! Подпишитесь на наши группы. Используйте кнопки ниже."
BUTTON_VERIFY = "Проверить подписку"
BUTTON_APPLY = "Оставить заявку"
BUTTON_SALAM = "Кинуть салам)))"
BUTTON_INVOICE = "Проверка накладной"

SECOND_MENU = {
    "inline_keyboard": [
        [{"text": BUTTON_APPLY, "callback_data": "apply"}],
        [{"text": BUTTON_SALAM, "callback_data": "salam"}],
        [{"text": BUTTON_INVOICE, "callback_data": "invoice"}],
    ]
}

# Pending admin actions keyed by admin user_id
pending_admin_actions: dict[int, str] = {}

# Pending invoice checks keyed by user_id
invoice_sessions: dict[int, dict] = {}


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
            self.widget.insert(tk.END, msg + "\n")
            self.widget.yview(tk.END)

        self.widget.after(0, append)


def enable_copy_paste(widget: tk.Widget):
    """Allow copying and pasting via context menu."""
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
    widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))


def start_log_window() -> tk.Tk:
    """Create a window that displays log messages and return it."""

    window = tk.Tk()
    window.title("Логи бота")
    frame = tk.Frame(window)
    frame.pack(fill="x")

    cpu_label = tk.Label(frame, text="CPU")
    cpu_label.grid(row=0, column=0, sticky="w")
    cpu_canvas = tk.Canvas(frame, width=200, height=20)
    cpu_canvas.grid(row=0, column=1, padx=5)

    mem_label = tk.Label(frame, text="RAM")
    mem_label.grid(row=1, column=0, sticky="w")
    mem_canvas = tk.Canvas(frame, width=200, height=20)
    mem_canvas.grid(row=1, column=1, padx=5, pady=(0, 5))

    text = scrolledtext.ScrolledText(window, width=80, height=20)
    text.pack(expand=True, fill="both")
    text.bind("<Key>", lambda e: "break")  # prevent edits but allow selection
    enable_copy_paste(text)
    handler = TkLogHandler(text)
    logging.getLogger().addHandler(handler)

    inv = tk.LabelFrame(window, text="FSRAR проверка")
    inv.pack(fill="x", padx=5, pady=5)
    tk.Label(inv, text="TNN").grid(row=0, column=0, sticky="e")
    ent_tnn = tk.Entry(inv, width=20)
    ent_tnn.grid(row=0, column=1, sticky="w")
    enable_copy_paste(ent_tnn)
    tk.Label(inv, text="FSRAR ID").grid(row=1, column=0, sticky="e")
    ent_fsrar = tk.Entry(inv, width=20)
    ent_fsrar.grid(row=1, column=1, sticky="w")
    enable_copy_paste(ent_fsrar)

    def start_invoice():
        tnn = ent_tnn.get().strip()
        if not tnn:
            messagebox.showerror("Ошибка", "Укажите номер ТТН")
            return
        fsrar = ent_fsrar.get().strip()
        if not fsrar:
            messagebox.showerror("Ошибка", "Укажите FSRAR ID")
            return
        cap = fetch_captcha()
        if not cap:
            messagebox.showerror("Ошибка", "Не удалось получить капчу")
            return
        image, headers, html = cap
        cap_win = tk.Toplevel(window)
        cap_win.title("Введите капчу")
        if PIL_AVAILABLE:
            img = Image.open(io.BytesIO(image))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(cap_win, image=photo)
            lbl.image = photo
            lbl.pack()
        else:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(image)
            tmp.close()
            tk.Label(cap_win, text=f"Капча сохранена в {tmp.name}").pack()
        ent_cap = tk.Entry(cap_win)
        ent_cap.pack()
        enable_copy_paste(ent_cap)

        def finish():
            captcha = ent_cap.get().strip()
            res = submit_invoice(tnn, fsrar, captcha, headers, html)
            res_win = tk.Toplevel(window)
            res_win.title("Результат проверки")
            txt = scrolledtext.ScrolledText(res_win, width=80, height=20)
            txt.pack(expand=True, fill="both")
            txt.bind("<Key>", lambda e: "break")
            txt.insert(tk.END, res or "Ошибка при проверке накладной")
            enable_copy_paste(txt)
            if FSRAR_LOG.exists():
                txt.insert(tk.END, "\n\n----- fsrar.log -----\n")
                try:
                    txt.insert(tk.END, FSRAR_LOG.read_text(encoding="utf-8"))
                except Exception:
                    txt.insert(tk.END, FSRAR_LOG.read_text())
            cap_win.destroy()

        tk.Button(cap_win, text="Отправить", command=finish).pack()

    tk.Button(inv, text="Запросить", command=start_invoice).grid(row=2, column=0, columnspan=2, pady=2)

    def color_from_percent(p: float) -> str:
        r = int(255 * p / 100)
        g = int(255 * (1 - p / 100))
        return f"#{r:02x}{g:02x}00"

    def update_usage():
        if PSUTIL_AVAILABLE:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent

            for canvas, value in ((cpu_canvas, cpu), (mem_canvas, mem)):
                canvas.delete("all")
                width = int(canvas["width"])
                color = color_from_percent(value)
                canvas.create_rectangle(0, 0, width, 20, fill="white")
                canvas.create_rectangle(0, 0, width * value / 100, 20, fill=color)
                canvas.create_text(width / 2, 10, text=f"{value:.0f}%")

        window.after(1000, update_usage)

    update_usage()
    return window


def configure_gui():
    """Show a configuration window and save results to files."""
    global TOKEN, ADMIN_IDS, required_groups

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
        config["token"] = TOKEN
        config["admin_ids"] = ADMIN_IDS
        save_config(config)
        save_groups(required_groups)
        root.destroy()

    tk.Button(root, text="Запустить", command=on_start).grid(row=4, column=0, columnspan=2, pady=5)
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


def load_authorized_users() -> list[int]:
    if AUTHORIZED_USERS_FILE.exists():
        try:
            with AUTHORIZED_USERS_FILE.open() as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return []
    return []


def save_authorized_users(data: list[int]):
    AUTHORIZED_USERS_FILE.write_text(json.dumps(data))


config = load_config()

users = load_users()
authorized_users = load_authorized_users()


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


def record_authorized_user(user_id: int):
    if user_id not in authorized_users:
        authorized_users.append(user_id)
        save_authorized_users(authorized_users)


def configure():
    """Load configuration from disk and open the GUI to edit it."""
    global TOKEN, API_URL, ADMIN_IDS, required_groups
    global WELCOME_TEXT, BUTTON_VERIFY

    logging.info("Loading configuration")
    TOKEN = config.get("token", "")
    ADMIN_IDS[:] = config.get("admin_ids", [])
    WELCOME_TEXT = config.get("welcome_text", WELCOME_TEXT)
    BUTTON_VERIFY = config.get("button_verify", BUTTON_VERIFY)
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

ADMIN_KEYBOARD = {
    "keyboard": [
        ["Список групп", "Добавить группу", "Удалить группу"],
        ["Изменить приветствие"],
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
        "",  # blank line separates headers from file data
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


def fetch_captcha() -> tuple[bytes, dict] | None:
    """Retrieve captcha image and session cookies from FSRAR site."""
    url = "https://check1.fsrar.ru/?AspxAutoDetectCookieSupport=1"
    try:
        logging.info("Fetching captcha page: %s", url)
        fsrar_logger.info("Fetching captcha page: %s", url)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=UNVERIFIED_CONTEXT) as resp:
            cookies = resp.headers.get_all("Set-Cookie") or []
            enc = resp.headers.get_content_charset() or "cp1251"
            html = resp.read().decode(enc, "ignore")
        match = re.search(r'<img[^>]+src="([^"]*captcha[^\"]*)"', html, re.I)
        if not match:
            return None
        cap_url = urllib.parse.urljoin(url, match.group(1))
        logging.info("Fetching captcha image: %s", cap_url)
        fsrar_logger.info("Fetching captcha image: %s", cap_url)
        req2 = urllib.request.Request(cap_url, headers={"Cookie": "; ".join(cookies)})
        with urllib.request.urlopen(req2, context=UNVERIFIED_CONTEXT) as resp2:
            image = resp2.read()
        return image, {"Cookie": "; ".join(cookies)}, html
    except Exception as exc:  # pragma: no cover - network errors
        logging.error("Failed to fetch captcha: %s", exc)
        fsrar_logger.error("Failed to fetch captcha: %s", exc)
        return None


def extract_field(page: str, label: str) -> str | None:
    """Return value that follows the given label on the results page."""
    # Table-based layout
    pattern = re.compile(
        rf"<td[^>]*>\s*{re.escape(label)}\s*</td>\s*<td[^>]*>(.*?)</td>",
        re.I | re.S,
    )
    m = pattern.search(page)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        return html.unescape(val)

    # Fallback: label followed by colon and text
    pattern = re.compile(rf"{re.escape(label)}[^:<]*[:>]\s*([^<]+)", re.I | re.S)
    m = pattern.search(page)
    if m:
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        return html.unescape(val)
    return None


def find_field_name(html: str, part: str, default: str) -> str:
    """Return the first field name containing ``part`` if present."""
    m = re.search(rf'name="([^"]*{re.escape(part)}[^"]*)"', html, re.I)
    return m.group(1) if m else default


def find_captcha_input(html: str) -> str:
    """Return the visible captcha input field name."""
    for inp in re.findall(r"<input[^>]+>", html, re.I):
        if "captcha" not in inp.lower():
            continue
        if 'type="hidden"' in inp.lower():
            continue
        m = re.search(r'name="([^"]+)"', inp, re.I)
        if m:
            return m.group(1)
    return find_field_name(html, "CaptchaCode", "CaptchaCode")


def find_fsrar_checkbox(html: str) -> str | None:
    """Return the checkbox name enabling the FSRAR ID field, if any."""
    for inp in re.findall(r"<input[^>]+>", html, re.I):
        if "checkbox" not in inp.lower():
            continue
        if "fsrar" in inp.lower() or "client" in inp.lower():
            m = re.search(r'name="([^"]+)"', inp, re.I)
            if m:
                return m.group(1)
    return None


def parse_form(html: str) -> dict:
    """Return a dict of form field names and values (inputs and selects)."""
    data: dict[str, str] = {}
    for inp in re.findall(r"<input[^>]+>", html, re.I):
        name_m = re.search(r'name="([^"]+)"', inp, re.I)
        if not name_m:
            continue
        name = name_m.group(1)
        value_m = re.search(r'value="([^"]*)"', inp, re.I)
        value = value_m.group(1) if value_m else ""
        if re.search(r'type="radio"', inp, re.I):
            if "checked" not in inp.lower():
                continue
        if re.search(r'type="checkbox"', inp, re.I):
            if "checked" in inp.lower():
                data[name] = value
            continue
        data[name] = value

    for name, opts in re.findall(r'<select[^>]+name="([^"]+)"[^>]*>(.*?)</select>', html, re.I | re.S):
        selected = re.search(r'<option[^>]+selected[^>]*value="([^"]*)"', opts, re.I)
        if not selected:
            selected = re.search(r'<option[^>]*value="([^"]*)"', opts, re.I)
        if selected:
            data[name] = selected.group(1)
    return data


def submit_invoice(tnn: str, fsrar: str, captcha: str, headers: dict, html: str) -> str | None:
    """Submit invoice data and parse result from FSRAR site."""
    url = "https://check1.fsrar.ru/?AspxAutoDetectCookieSupport=1"
    try:
        viewstate = re.search(r'name="__VIEWSTATE" value="([^"]+)"', html)
        eventvalidation = re.search(r'name="__EVENTVALIDATION" value="([^"]+)"', html)
        viewgen = re.search(r'name="__VIEWSTATEGENERATOR" value="([^"]+)"', html)

        reg_field = find_field_name(html, "RegId", "RegId")
        fsrar_field = find_field_name(html, "ClientId", "ClientId")
        cap_field = find_captcha_input(html)
        btn_field = find_field_name(html, "btn", "btnSend")
        search_field = find_field_name(html, "Search", "")

        form = parse_form(html)
        form[reg_field] = tnn
        form[fsrar_field] = fsrar
        form[cap_field] = captcha
        fsrar_chk = find_fsrar_checkbox(html)
        if fsrar_chk:
            form[fsrar_chk] = form.get(fsrar_chk, "on") or "on"
        if search_field:
            form[search_field] = reg_field
        if btn_field in form and not form[btn_field]:
            form[btn_field] = ""  # value usually irrelevant
        if viewstate:
            form["__VIEWSTATE"] = viewstate.group(1)
        if eventvalidation:
            form["__EVENTVALIDATION"] = eventvalidation.group(1)
        if viewgen:
            form["__VIEWSTATEGENERATOR"] = viewgen.group(1)
        data_encoded = urllib.parse.urlencode(form).encode()
        req_headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        req_headers.update(headers)
        logging.info("Invoice request to %s: %s", url, form)
        fsrar_logger.info("Invoice request to %s: %s", url, form)
        req = urllib.request.Request(url, data=data_encoded, headers=req_headers)
        with urllib.request.urlopen(req, context=UNVERIFIED_CONTEXT) as resp:
            enc = resp.headers.get_content_charset() or "cp1251"
            page = resp.read().decode(enc, "ignore")
        logging.info("FSRAR response length: %d", len(page))
        fsrar_logger.info("FSRAR response length: %d", len(page))
        logging.debug("FSRAR response snippet: %s", page[:200])
        fsrar_logger.debug("FSRAR response snippet: %s", page[:200])

        pairs = re.findall(
            r"<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", page, re.I | re.S
        )
        if pairs:
            lines = []
            for lbl, val in pairs:
                lbl = re.sub(r"<[^>]+>", "", lbl)
                val = re.sub(r"<[^>]+>", "", val)
                lbl = re.sub(r"\s+", " ", lbl).strip()
                val = re.sub(r"\s+", " ", val).strip()
                lbl = html.unescape(lbl)
                val = html.unescape(val)
                lines.append(f"{lbl}: {val}")
            return "\n".join(lines)
        parts = []
        date = extract_field(page, "изменения")
        if date:
            parts.append(f"Дата и время последнего изменения: {date}")
        status = extract_field(page, "Статус")
        if status:
            parts.append(f"Статус: {status}")
        owner = extract_field(page, "Кому принадлежит")
        if owner:
            parts.append(f"Кому принадлежит: {owner}")
        return "\n".join(parts) if parts else "Нет данных"
    except Exception as exc:  # pragma: no cover - network errors
        logging.error("Failed to submit invoice: %s", exc)
        fsrar_logger.error("Failed to submit invoice: %s", exc)
        return None


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

    if data == "verify":
        if check_subscriptions(user_id):
            record_authorized_user(user_id)
            send_message(chat_id, ACCESS_GRANTED_MSG, SECOND_MENU)
        else:
            send_message(chat_id, ACCESS_DENIED_MSG)
    elif data == "apply":
        send_message(chat_id, "Заявка отправлена")
    elif data == "salam":
        send_message(chat_id, "Салам алейкум!")
    elif data == "invoice":
        invoice_sessions[user_id] = {"stage": "tnn"}
        send_message(chat_id, "Введите номер ТТН (например, 123456789)")
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
        return

    if user_id in invoice_sessions:
        session = invoice_sessions[user_id]
        stage = session.get("stage")
        if stage == "tnn":
            session["tnn"] = text.strip()
            session["stage"] = "fsrar"
            send_message(chat_id, "Введите FSRAR ID получателя (например, 030000000000)")
        elif stage == "fsrar":
            session["fsrar"] = text.strip()
            cap = fetch_captcha()
            if cap:
                image, headers, html = cap
                session.update({"stage": "captcha", "headers": headers, "html": html})
                with open("captcha.jpg", "wb") as fh:
                    fh.write(image)
                send_photo(chat_id, "captcha.jpg", "Введите капчу")
            else:
                send_message(chat_id, "Не удалось получить капчу")
                invoice_sessions.pop(user_id, None)
        elif stage == "captcha":
            result = submit_invoice(
                session.get("tnn", ""),
                session.get("fsrar", ""),
                text.strip(),
                session.get("headers", {}),
                session.get("html", ""),
            )
            if result:
                send_message(chat_id, result)
            else:
                send_message(chat_id, "Ошибка при проверке накладной")
            invoice_sessions.pop(user_id, None)
        return

    if text.startswith("/start"):
        logging.info("/start command from %s", user_id)
        if user_id in authorized_users:
            send_message(chat_id, ACCESS_GRANTED_MSG, SECOND_MENU)
            return
        group_buttons = [
            [{"text": f"Группа {i+1}", "url": grp.get("link") or str(grp.get("id"))}]
            for i, grp in enumerate(required_groups)
        ]
        keyboard = {
            "inline_keyboard": group_buttons
            + [[{"text": BUTTON_VERIFY, "callback_data": "verify"}]]
        }
        send_message(chat_id, WELCOME_TEXT, keyboard)
    elif text.startswith("/verify"):
        logging.info("/verify command from %s", user_id)
        if check_subscriptions(user_id):
            record_authorized_user(user_id)
            send_message(chat_id, ACCESS_GRANTED_MSG, SECOND_MENU)
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

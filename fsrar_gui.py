import json
import logging
import urllib.parse
import io
from tkinter import Tk, Toplevel, Label, Entry, Button, messagebox
from PIL import Image, ImageTk
import requests
from bs4 import BeautifulSoup
import re

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger("fsrar_gui")
logger.setLevel(logging.DEBUG)
_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_file_handler = logging.FileHandler("fsrar_cli.log", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(_formatter)
_stream_handler = logging.StreamHandler()
_stream_handler.setLevel(logging.INFO)
_stream_handler.setFormatter(_formatter)
logger.addHandler(_file_handler)
logger.addHandler(_stream_handler)

BASE_URL = "https://check1.fsrar.ru/"
API_URL = urllib.parse.urljoin(BASE_URL, "MobileApi/transportwb")

session: requests.Session | None = None
captcha_id = ""
instance_id = ""


def fetch_captcha(sess: requests.Session):
    logger.info("Получение капчи с %s", BASE_URL)
    logger.debug("GET %s", BASE_URL)
    resp = sess.get(BASE_URL, verify=False)
    logger.debug("Response status=%s", resp.status_code)
    try:
        with open("captcha_page.html", "w", encoding="utf-8") as fh:
            fh.write(resp.text)
    except Exception:
        logger.exception("Failed to save captcha page")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    cap_id_el = (
        soup.find("input", {"name": "CaptchaId"})
        or soup.find("input", {"id": "CaptchaId"})
        or soup.find("input", {"name": re.compile("captcha", re.I)})
        or soup.find("input", {"id": re.compile("captcha", re.I)})
    )
    inst_id_el = (
        soup.find("input", {"name": "InstanceId"})
        or soup.find("input", {"id": "InstanceId"})
        or soup.find("input", {"name": re.compile("instance", re.I)})
        or soup.find("input", {"id": re.compile("instance", re.I)})
    )
    img_el = (
        soup.find("img", {"id": re.compile("captcha", re.I)})
        or soup.find("img", {"class": re.compile("captcha", re.I)})
    )
    if not (cap_id_el and inst_id_el and img_el):
        logger.error("Captcha elements not found")
        raise RuntimeError("Не удалось извлечь данные капчи")
    return cap_id_el.get("value"), inst_id_el.get("value"), urllib.parse.urljoin(BASE_URL, img_el.get("src"))


def send_request(ttn: str, receiver: str, user_input: str):
    payload = {
        "id": ttn,
        "owner_id": "",
        "owner_receiver": receiver,
        "CaptchaId": captcha_id,
        "InstanceId": instance_id,
        "UserInput": user_input,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
        "Referer": BASE_URL,
    }
    logger.info("Отправка POST-запроса")
    logger.debug("POST %s", API_URL)
    resp = session.post(API_URL, data=payload, headers=headers, verify=False)
    logger.debug("Response status=%s", resp.status_code)
    logger.debug("Response text: %s", resp.text[:200])
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        logger.exception("Некорректный ответ")
        messagebox.showerror("Ошибка", "Некорректный ответ от сервера")
        return
    logger.info("Ответ: %s", data)
    messagebox.showinfo("Ответ", json.dumps(data, ensure_ascii=False, indent=2))


def open_captcha_window(ttn: str, receiver: str, url: str):
    win = Toplevel()
    win.title("Введите капчу")
    resp = session.get(url, verify=False)
    img = Image.open(io.BytesIO(resp.content))
    photo = ImageTk.PhotoImage(img)
    lbl = Label(win, image=photo)
    lbl.image = photo
    lbl.pack(padx=10, pady=10)

    entry = Entry(win)
    entry.pack(padx=10, pady=5)
    entry.focus_set()

    def submit():
        code = entry.get().strip()
        if not code:
            messagebox.showerror("Ошибка", "Введите капчу")
            return
        win.destroy()
        send_request(ttn, receiver, code)

    btn = Button(win, text="Отправить", command=submit)
    btn.pack(padx=10, pady=5)
    win.grab_set()


def start():
    ttn = ttn_entry.get().strip()
    receiver = recv_entry.get().strip()
    if not ttn or not receiver:
        messagebox.showerror("Ошибка", "Введите номер ТТН и ФСРАР ID")
        return
    global session, captcha_id, instance_id
    session = requests.Session()
    try:
        captcha_id, instance_id, url = fetch_captcha(session)
    except Exception as e:
        logger.exception("Ошибка при получении капчи")
        messagebox.showerror("Ошибка", str(e))
        return
    open_captcha_window(ttn, receiver, url)


root = Tk()
root.title("Проверка накладной FSRAR")

Label(root, text="Номер ТТН:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
Label(root, text="ФСРАР ID получателя:").grid(row=1, column=0, padx=5, pady=5, sticky="e")

ttn_entry = Entry(root)
ttn_entry.grid(row=0, column=1, padx=5, pady=5)
recv_entry = Entry(root)
recv_entry.grid(row=1, column=1, padx=5, pady=5)

btn = Button(root, text="Далее", command=start)
btn.grid(row=2, column=0, columnspan=2, pady=10)

root.mainloop()

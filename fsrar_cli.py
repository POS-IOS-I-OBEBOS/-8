import json
import logging
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

requests.packages.urllib3.disable_warnings()

logger = logging.getLogger("fsrar_cli")
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


def fetch_captcha(session: requests.Session):
    """Return CaptchaId, InstanceId and captcha image URL."""
    logger.info("Получение капчи с %s", BASE_URL)
    logger.debug("GET %s", BASE_URL)
    resp = session.get(BASE_URL, verify=False)
    logger.debug("Response status=%s", resp.status_code)
    logger.debug("Response html: %s", resp.text[:200])
    try:
        with open("captcha_page.html", "w", encoding="utf-8") as fh:
            fh.write(resp.text)
        logger.debug("Captcha page saved to captcha_page.html")
    except Exception:
        logger.exception("Failed to save captcha page")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # try several attribute combinations as the exact ids can change
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

    captcha_id = cap_id_el.get("value")
    instance_id = inst_id_el.get("value")
    captcha_url = urllib.parse.urljoin(BASE_URL, img_el.get("src"))
    logger.info("Получены значения CaptchaId=%s InstanceId=%s", captcha_id, instance_id)
    return captcha_id, instance_id, captcha_url


def check_document(ttn: str, receiver: str):
    logger.info("Проверка документа. ТТН=%s, ФСРАР=%s", ttn, receiver)
    session = requests.Session()
    captcha_id, instance_id, captcha_url = fetch_captcha(session)

    print("Откройте изображение капчи по ссылке:", captcha_url)
    logger.info("URL капчи: %s", captcha_url)
    user_input = input("Введите капчу: ").strip()
    logger.info("Введена капча: %s", user_input)

    payload = {
        "id": ttn,
        "owner_id": "",
        "owner_receiver": receiver,
        "CaptchaId": captcha_id,
        "InstanceId": instance_id,
        "UserInput": user_input,
    }
    logger.debug("Формирование запроса: %s", payload)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
        "Referer": BASE_URL,
    }

    logger.info("Отправка POST-запроса")
    logger.debug("Headers: %s", headers)

    logger.debug("POST %s", API_URL)
    resp = session.post(API_URL, data=payload, headers=headers, verify=False)
    logger.debug("Response status=%s", resp.status_code)
    logger.debug("Response text: %s", resp.text[:200])
    resp.raise_for_status()
    logger.info("Ответ status=%s", resp.status_code)
    try:
        data = resp.json()
    except Exception:
        logger.exception("Некорректный ответ")
        print("Некорректный ответ:")
        print(resp.text)
        return
    logger.info("Ответ от сервера: %s", data)
    print("Ответ от сервера:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logger.info("Запуск утилиты")
    ttn = input("Введите номер ТТН: ").strip()
    receiver = input("Введите ФСРАР ID получателя: ").strip()
    check_document(ttn, receiver)

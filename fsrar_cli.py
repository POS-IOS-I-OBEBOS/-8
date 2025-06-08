import json
import logging
import requests
from bs4 import BeautifulSoup
import urllib.parse

requests.packages.urllib3.disable_warnings()

logging.basicConfig(
    filename="fsrar_cli.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

BASE_URL = "https://check1.fsrar.ru/"
API_URL = urllib.parse.urljoin(BASE_URL, "MobileApi/transportwb")


def fetch_captcha(session: requests.Session):
    """Return CaptchaId, InstanceId and captcha image URL."""
    logging.info("Получение капчи с %s", BASE_URL)
    resp = session.get(BASE_URL, verify=False)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cap_id_el = soup.find("input", {"name": "CaptchaId"})
    inst_id_el = soup.find("input", {"name": "InstanceId"})
    img_el = soup.find("img", {"id": "captcha"})

    if not (cap_id_el and inst_id_el and img_el):
        raise RuntimeError("Не удалось извлечь данные капчи")

    captcha_id = cap_id_el.get("value")
    instance_id = inst_id_el.get("value")
    captcha_url = urllib.parse.urljoin(BASE_URL, img_el.get("src"))
    logging.info("Получены значения CaptchaId=%s InstanceId=%s", captcha_id, instance_id)
    return captcha_id, instance_id, captcha_url


def check_document(ttn: str, receiver: str):
    logging.info("Проверка документа. ТТН=%s, ФСРАР=%s", ttn, receiver)
    session = requests.Session()
    captcha_id, instance_id, captcha_url = fetch_captcha(session)

    print("Откройте изображение капчи по ссылке:", captcha_url)
    logging.info("URL капчи: %s", captcha_url)
    user_input = input("Введите капчу: ").strip()
    logging.info("Введена капча: %s", user_input)

    payload = {
        "id": ttn,
        "owner_id": "",
        "owner_receiver": receiver,
        "CaptchaId": captcha_id,
        "InstanceId": instance_id,
        "UserInput": user_input,
    }
    logging.info("Формирование запроса: %s", payload)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
        "Referer": BASE_URL,
    }

    logging.info("Отправка POST-запроса")

    resp = session.post(API_URL, data=payload, headers=headers, verify=False)
    resp.raise_for_status()
    logging.info("Ответ status=%s", resp.status_code)
    try:
        data = resp.json()
    except Exception:
        logging.error("Некорректный ответ: %s", resp.text)
        print("Некорректный ответ:")
        print(resp.text)
        return
    logging.info("Ответ от сервера: %s", data)
    print("Ответ от сервера:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.info("Запуск утилиты")
    ttn = input("Введите номер ТТН: ").strip()
    receiver = input("Введите ФСРАР ID получателя: ").strip()
    check_document(ttn, receiver)

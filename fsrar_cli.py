import json
import requests
from bs4 import BeautifulSoup
import urllib.parse

requests.packages.urllib3.disable_warnings()

BASE_URL = "https://check1.fsrar.ru/"
API_URL = urllib.parse.urljoin(BASE_URL, "MobileApi/transportwb")


def fetch_captcha(session: requests.Session):
    """Return CaptchaId, InstanceId and captcha image URL."""
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
    return captcha_id, instance_id, captcha_url


def check_document(ttn: str, receiver: str):
    session = requests.Session()
    captcha_id, instance_id, captcha_url = fetch_captcha(session)

    print("Откройте изображение капчи по ссылке:", captcha_url)
    user_input = input("Введите капчу: ").strip()

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

    resp = session.post(API_URL, data=payload, headers=headers, verify=False)
    resp.raise_for_status()
    try:
        data = resp.json()
    except Exception:
        print("Некорректный ответ:")
        print(resp.text)
        return
    print("Ответ от сервера:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ttn = input("Введите номер ТТН: ").strip()
    receiver = input("Введите ФСРАР ID получателя: ").strip()
    check_document(ttn, receiver)

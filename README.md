# Telegram Bot

This bot verifies that users are subscribed to the specified Telegram channels before granting them access to the second menu. On the first launch it asks for the bot token, administrator IDs and the IDs and invite links of the required channels. These settings are saved to `config.json` so subsequent runs do not prompt again.

Users interact with the bot via inline buttons. After `/start` the bot sends buttons linking to the required channels along with a single **Проверить подписку** button. If the user is subscribed to all channels they receive an authorised status and a new menu with buttons **Оставить заявку**, **Кинуть салам)))** и **Проверка накладной**.

## Running

```bash
python bot.py
```
When starting, a graphical window will appear asking for the bot token,
administrator IDs and channel IDs with invite links. Example values are shown in the fields. After pressing
"Запустить" the bot starts and a separate log window displays all
operations. The log window also shows real-time graphs for CPU and
memory usage: bars fill from green to red as load increases. You can copy
any text from this window or paste values using the standard clipboard
shortcuts. If an error occurs it is described in the log window along with a suggestion for how
to fix it. The bottom of the log window contains a small form for
checking invoices on the FSRAR service: enter the TNN and FSRAR ID and
press "Запросить". A captcha appears in a new window with a field for the
text. After sending the captcha another window shows the invoice details
and the contents of `fsrar.log`.

## Building an executable

To create a standalone Windows executable you can use [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile bot.py
```

The resulting `dist/bot.exe` behaves like running `python bot.py`. After
launching, the configuration window is shown and then a separate log window
displays all actions while the bot is running.

The admin panel is opened with `/admin` and uses a custom keyboard. It lets
administrators view or edit channel links, change the welcome message,
see basic statistics and request a visit chart in JPG format. Authorised
users also have access to the **Проверка накладной** button.

When pressed, the bot first asks for the TNN number (for example `123456789`).
The bot will prepend `TTN-` to this value and select the search mode
"Поиск по Идентификатору накладной" automatically. It then requests the recipient's
FSRAR ID (for example `030000000000`). The bot turns on the option "fsrar ID получателя"
when submitting the form. After the
user enters these values the bot shows a captcha from
<https://check1.fsrar.ru>. Once the captcha text is sent, the bot waits for the
FSRAR service to respond and returns every field from the results table. Each
label and value found on the page is sent back in a separate line so users see
all information provided by the site. Certificate verification is disabled when
contacting this site to avoid SSL errors. The invoice submission automatically
detects the actual form field names and search mode on the site, ensuring the
query succeeds even if these names change. Pages are decoded using the
`windows-1251` encoding reported by the server, so Russian text is parsed
correctly. The bot writes all request and response details to `fsrar.log` so
invoice problems can be diagnosed. HTML entities on the page are decoded so
Russian characters display correctly in the bot messages.

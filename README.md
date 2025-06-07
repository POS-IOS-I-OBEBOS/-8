# Telegram Bot

This bot verifies that users are subscribed to the specified Telegram channels before granting them access to the second menu. On the first launch it asks for the bot token, administrator IDs and the IDs and invite links of the required channels. These settings are saved to `config.json` so subsequent runs do not prompt again.

Users interact with the bot via inline buttons. After `/start` the bot sends buttons linking to the required channels along with a single **Проверить подписку** button. If the user is subscribed to all channels they receive an authorised status and a new menu with buttons **Оставить заявку** and **Кинуть салам)))**.

## Running

```bash
python bot.py
```
When starting, a graphical window will appear asking for the bot token,
administrator IDs and channel IDs with invite links. Example values are shown in the fields. After pressing
"Запустить" the bot starts and a separate log window displays all
operations. The log window also shows real-time graphs for CPU and
memory usage: bars fill from green to red as load increases. If an error
occurs it is described in the log window along with a suggestion for how
to fix it.

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
see basic statistics and request a visit chart in JPG format.

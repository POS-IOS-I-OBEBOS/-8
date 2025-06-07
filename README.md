# Telegram Bot

This bot checks whether users are subscribed to one or more Telegram groups before granting them a separate invite link. At first launch it asks for the bot token, administrator IDs, invite links to the required groups and the exclusive link. These settings are saved to `config.json` so subsequent runs do not prompt again.

Users interact with the bot via inline buttons. After `/start` the bot
отправляет список групп в виде кнопок, а также кнопки:

- Запросить список групп заново
- Проверить подписку
- Получить эксклюзивную ссылку

## Running

```bash
python bot.py
```
When starting, a graphical window will appear asking for the bot token,
administrator IDs, links to the required groups and the invite link for
exclusive access. Example values are shown in the fields. After pressing
"Запустить" the bot starts and a separate log window displays all
operations. If an error occurs it is described in the log window along
with a suggestion for how to fix it.

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
administrators view/edit group links, change the welcome message and user button
labels, see basic statistics and request a visit chart in JPG format.

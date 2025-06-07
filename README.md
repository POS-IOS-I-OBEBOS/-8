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
At first run the program will ask for:
- the bot token
- administrator IDs
- invite links for the groups that users must join
- the invite link to send after successful verification

## Building an executable

To create a standalone Windows executable you can use [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile bot.py
```

The resulting `dist/bot.exe` will behave the same as running `python bot.py`.
When started a console window will appear asking for configuration data on first
run and showing log messages while the bot is running.

The admin panel is opened with `/admin` and uses a custom keyboard. It lets
administrators view/edit group links, change the welcome message and user button
labels, see basic statistics and request a visit chart in JPG format.

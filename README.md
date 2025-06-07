# Telegram Bot

This bot checks user subscriptions to specified Telegram groups and provides a small admin panel to manage those groups. When started it will ask for the bot token and a list of administrator user IDs.

## Running

```bash
python bot.py
```
The program will request your Telegram bot token and admin IDs separated by commas.

## Building an executable

To create a standalone Windows executable you can use [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile bot.py
```

The resulting `dist/bot.exe` will behave the same as running `python bot.py`.

# Telegram Bot

This bot checks whether users are subscribed to a set of Telegram channels before granting them access to an invite link. On launch it asks for the bot token, admin IDs, the channel IDs to check and the invite link for exclusive access.

Users interact with the bot via inline buttons. After `/start` they can:

- Request the list of required channels
- Verify their subscriptions
- Receive the invite link once all subscriptions are confirmed

## Running

```bash
python bot.py
```
The program will ask for:
- the bot token
- administrator IDs
- channel IDs for subscription checks
- the invite link to send to subscribed users

## Building an executable

To create a standalone Windows executable you can use [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile bot.py
```

The resulting `dist/bot.exe` will behave the same as running `python bot.py`.

The admin panel is available via `/admin` and provides buttons to view and edit the channel list as well as basic statistics about registered users.

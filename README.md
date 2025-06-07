# Telegram Bot

This bot checks whether users are subscribed to one or more Telegram groups before granting them a separate invite link. At first launch it asks for the bot token, administrator IDs, invite links to the required groups and the exclusive link. These settings are saved to `config.json` so subsequent runs do not prompt again.

Users interact with the bot via inline buttons. After `/start` they can:

- Request the list of required groups (shown as clickable buttons)
- Verify their subscriptions
- Receive the invite link once all subscriptions are confirmed

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

The admin panel is available via `/admin` and provides buttons to view or edit the list of required groups and to see basic statistics about registered and verified users.

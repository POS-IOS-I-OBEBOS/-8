# Telegram Bot

This bot checks whether users are subscribed to one or more Telegram channels before granting them a separate invite link. On first start the script asks for the bot token, administrator IDs, the IDs of the channels to verify and the invite links that should be shown to users. All entered data is validated with the Telegram API and then stored in `config.json` and `groups.json` so the bot does not prompt again.

Users interact with the bot via inline buttons. After `/start` they can:

- Request the list of required groups (shown as clickable buttons)
- Verify their subscriptions
- Receive the invite link once all subscriptions are confirmed

## Running

```bash
python bot.py
```
At first run the program will ask for:
- the bot token (for example `123456:ABCDEF`)
- administrator IDs separated by commas
- IDs of the channels to check (for example `-1001234567890` or `@publicchannel`)
- invite links to these channels that will be shown to users
- the invite link to send after successful verification
All data is checked with the Telegram API before the bot continues working.

## Building an executable

To create a standalone Windows executable you can use [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile bot.py
```

The resulting `dist/bot.exe` will behave the same as running `python bot.py`.

The admin panel is available via `/admin` and provides buttons to view or edit the list of required groups and to see basic statistics about registered and verified users.

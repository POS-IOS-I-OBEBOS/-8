# Telegram KitchenResources Editor

This bot allows editing a `KitchenResources.xml` file used in iiko KDS panels.

## Setup
1. Install Python 3.11+ and **install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. Place your `KitchenResources.xml` file in the same directory as `bot.py`.
3. Run the bot directly with Python. On first launch you will be prompted for
   the Telegram bot token; it will be saved to `config.json` in the same
   directory for future runs.

If `pip install -r requirements.txt` fails when building `aiohttp`, upgrade pip and ensure you are using Python 3.11 or newer which has prebuilt wheels.

If you encounter `ModuleNotFoundError: No module named 'aiogram'`, make sure the
dependencies were installed with `pip install -r requirements.txt` before
running the bot.

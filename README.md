# Telegram KitchenResources Editor

This bot allows editing a `KitchenResources.xml` file used in iiko KDS panels.

## Setup
1. Install Python 3.11+ and **install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. Build the standalone executable with:
   ```bash
   pyinstaller bot.py
   ```
   The compiled binary will appear in `dist/`.
3. Copy your `KitchenResources.xml` file into the `dist` folder next to the
   executable.
4. Run the bot. On first launch you will be prompted for the Telegram bot token;
   it will be saved to `config.json` in the same directory for future runs.

If you encounter `ModuleNotFoundError: No module named 'aiogram'`, make sure the
dependencies were installed with `pip install -r requirements.txt` before
running or packaging the bot.

#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Calorie Tracker Bot

This bot will provide you with a calorie estimate for your meal based on the
picture you send. It will also specify the macronutrient content of the meal.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import os
import sys
import tempfile

import requests
from telegram import ForceReply, Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("Please set the TELEGRAM_BOT_TOKEN environment variable")
    sys.exit(1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome and instructions message when the command
    /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )
    await update.message.reply_text(
        "Send me pictures 📷 of your meals 🥗 where the food is clearly visible."
        "I'll provide you with a calorie estimate for it. "
        "I will also specify the macronutrient content of the meal."
    )
    await update.message.reply_text(
        "For example, in a sandwich 🥪, it is best to provide a picture of"
        "the open sandwich."
    )


async def kcal_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Calculate the calories in the meal."""
    # Get the photo file
    photo_id = update.message.photo[-1].file_id
    photo_file = await context.bot.get_file(photo_id)
    logger.debug("Photo file: %s", photo_file)

    response = requests.get(photo_file.file_path)
    with tempfile.NamedTemporaryFile(mode="w+b") as temp_file:
        temp_file.write(response.content)
        temp_file.flush()

    # Send a message to the user
    await update.message.reply_text(
        "Calculating the calories in the meal. Please wait a moment. 🕒"
    )

    # TODO: Request to the API with the image file and parse the JSON response.
    # For now, just send a dummy response
    await update.message.reply_text(
        "🍽️ *Gazpacho con jamón*"
        "\n_500 kcal_"
        "\n\n*Macronutrient content*"
        "\n💪 Protein: 20g"
        "\n🌾 Carbohydrates: 50g"
        "\n🧈 Fat: 25g",
        parse_mode="MarkdownV2",
    )


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, kcal_calculator))
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

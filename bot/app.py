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
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL")
if not BACKEND_BASE_URL:
    logger.error("Please set the BACKEND_BASE_URL environment variable")
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

    # Send a message to the user
    message = await update.message.reply_text(
        "Calculating the calories in the meal. Please wait a moment. 🕒"
    )

    try:
        response = requests.post(
            f"{BACKEND_BASE_URL}/meal?photo_url={photo_file.file_path}&user_id={update.effective_user.id}"
        )

        logger.info("Response from the API: %s", response.text)

        data_json = response.json()
        meal_name = data_json["meal_name"]
        calories = data_json["calories"]
        carbs = calories * (data_json["carbs"] / 100) / 4
        fat = calories * (data_json["carbs"] / 100) / 9
        protein = calories * (data_json["carbs"] / 100) / 4

        logger.info("Calories in the meal: %s", calories)
        logger.info("Protein in the meal: %s", protein)
        logger.info("Carbs in the meal: %s", carbs)
        logger.info("Fat in the meal: %s", fat)

    except requests.exceptions.RequestException as e:
        logger.error("Error in request to the API: %s", e)
        await update.message.reply_text(
            "Sorry, I was unable to calculate the calories in the meal. Please try again later."
        )
        return

    await message.edit_text(
        f"""🍽️ *{meal_name}*
  _{round(calories)} kcal_

*Macronutrient content*
  💪 Protein: {round(protein)} g
  🌾 Carbohydrates: {round(carbs)} g
  🧈 Fat: {round(fat)} g
""",
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

"""
main.py
Entry point for the Student Outreach Agent.
Initializes the data layer, LLM agent, and Telegram bot, then starts polling.
"""

import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from data_manager import DataManager
from agent import StudentAgent
from bot import cmd_start, cmd_register, cmd_trigger, cmd_status, handle_message

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set.")
        return

    # Initialize components
    dm = DataManager()
    agent = StudentAgent(data_manager=dm)

    # Build Telegram application
    app = Application.builder().token(token).build()
    app.bot_data["data_manager"] = dm
    app.bot_data["agent"] = agent

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("register", cmd_register))
    app.add_handler(CommandHandler("trigger", cmd_trigger))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Student Outreach Agent started. Listening for messages...")
    app.run_polling()


if __name__ == "__main__":
    main()

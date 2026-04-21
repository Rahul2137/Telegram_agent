"""
main.py
Entry point for the Student Outreach Agent and Dashboard.
Initializes and runs the FastAPI server, which in turn starts the Telegram bot.
"""

import os
import logging
import uvicorn
from dotenv import load_dotenv

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set.")
        return

    logger.info("Starting Student Outreach Dashboard and Agent...")
    uvicorn.run("dashboard_api:app", host="127.0.0.1", port=8010, reload=False)

if __name__ == "__main__":
    main()

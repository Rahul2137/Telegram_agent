"""
bot.py
Telegram command and message handlers.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from scheduler import run_all_tasks

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    dm = context.bot_data["data_manager"]
    student_list = dm.students[["student_id", "name", "course_id"]].to_string(index=False)

    text = (
        "Welcome to the Student Outreach Agent.\n\n"
        "Available commands:\n"
        "/register <student_id> — Link this chat to a student profile\n"
        "/trigger — Run all scheduled outreach tasks now\n"
        "/status — View your linked student profile\n\n"
        f"Student directory:\n```\n{student_list}\n```"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /register <student_id> to link a Telegram chat to a student."""
    dm = context.bot_data["data_manager"]
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /register <student_id>")
        return

    student_id = args[0].upper()
    student = dm.get_student(student_id)
    if not student:
        await update.message.reply_text(f"Student '{student_id}' not found in the database.")
        return

    chat_id = update.message.chat_id
    dm.register_chat_id(student_id, chat_id)
    course_name = dm.get_course_name(student["course_id"])

    await update.message.reply_text(
        f"Linked this chat to {student['name']} ({student_id}) — {course_name}."
    )
    logger.info("Registered chat %s → %s", chat_id, student_id)


async def cmd_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trigger to execute all scheduled tasks immediately."""
    await update.message.reply_text("Running all scheduled outreach tasks...")
    await run_all_tasks(context)
    await update.message.reply_text("All tasks completed. Check your messages above.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status to show the linked student's profile."""
    dm = context.bot_data["data_manager"]
    chat_id = str(update.message.chat_id)
    student = dm.get_student_by_chat_id(chat_id)

    if not student:
        await update.message.reply_text("This chat is not linked to any student. Use /register first.")
        return

    sid = student["student_id"]
    context_text = dm.build_student_context(sid)
    await update.message.reply_text(f"```\n{context_text}\n```", parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text replies from students during active conversations."""
    agent = context.bot_data["agent"]
    dm = context.bot_data["data_manager"]
    chat_id = str(update.message.chat_id)
    user_text = update.message.text

    student = dm.get_student_by_chat_id(chat_id)
    if not student:
        return  # Ignore messages from unregistered users

    student_id = student["student_id"]
    if not agent.is_active(student_id):
        return  # No active conversation to continue

    reply = agent.handle_reply(student_id, user_text)
    await update.message.reply_text(reply)

    if not agent.is_active(student_id):
        await update.message.reply_text("_Conversation closed and logged._", parse_mode="Markdown")

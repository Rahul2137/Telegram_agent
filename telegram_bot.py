import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent import StudentAgent

# Note: This is a sandbox setup. In a real system, you would identify the student
# based on their Telegram User ID, mapped in your database. For this sandbox,
# we'll assume a test user mapping or let the user login.
# For simplicity, we'll map the sandbox tester to "alice_01"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler."""
    welcome_text = (
        "Welcome to the Student Agent Bot!\n\n"
        "To start a simulation, use the command:\n"
        "/simulate <student_id>\n\n"
        "Available student IDs:\n"
        "- alice_01 (Homework follow-up)\n"
        "- charlie_03 (Attendance follow-up)\n"
        "- bob_02 (Satisfaction survey)\n"
        "- diana_04 (Task reminder)"
    )
    await update.message.reply_text(welcome_text)

async def simulate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to start a specific scenario simulation."""
    args = context.args
    if not args:
        await update.message.reply_text("Please provide a student ID, e.g., /simulate alice_01")
        return
        
    student_id = args[0]
    agent = context.bot_data.get("agent")
    
    scenarios = {
        "alice_01": "Follow up on missing Homework 4",
        "charlie_03": "Follow up on poor attendance and see if they need help",
        "bob_02": "Conduct a quick mid-course satisfaction survey",
        "diana_04": "Remind about the Kaggle competition deadline this Sunday and optional Q&A tomorrow"
    }
    
    scenario = scenarios.get(student_id)
    if not scenario:
        await update.message.reply_text(f"Student ID '{student_id}' not found in mock_db or no scenario defined.")
        return
        
    context.user_data["current_student_id"] = student_id
    await update.message.reply_text(f"*(System: Starting simulation for {student_id}...)*", parse_mode='Markdown')
    
    reply = agent.start_interaction(student_id, scenario)
    await update.message.reply_text(f"🤖 {reply}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages from the student."""
    agent = context.bot_data.get("agent")
    user_text = update.message.text
    student_id = context.user_data.get("current_student_id")
    
    if not student_id or student_id not in agent.chats:
        await update.message.reply_text("No active simulation. Use /simulate <student_id> to start.")
        return
    
    # Send the user text to the agent
    reply = agent.handle_reply(student_id, user_text)
    
    # Send back to Telegram
    await update.message.reply_text(f"🤖 {reply}")
    
    if student_id not in agent.chats:
        await update.message.reply_text("*(System: Conversation ended and logged to CSV)*", parse_mode='Markdown')
        context.user_data["current_student_id"] = None

def main():
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set.")
        return

    # Initialize agent
    agent = StudentAgent()
    
    application = Application.builder().token(telegram_token).build()
    
    # Store agent in bot_data to access in handlers
    application.bot_data["agent"] = agent

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("simulate", simulate))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot started. Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()

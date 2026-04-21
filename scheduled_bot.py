import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

class ScheduledAgent:
    def __init__(self, db_path="mock_db.json", sheet_path="tracking_sheet.csv"):
        self.db_path = db_path
        self.sheet_path = sheet_path
        
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_key:
            logging.warning("OPENAI_API_KEY not set. API calls will fail.")
            
        self.llm_client = OpenAI(api_key=self.openai_key)
        self.model_name = "gpt-4o-mini"
        
        self.load_db()
        self.chats = {} # Track active conversations by student_id
        
        if not os.path.exists(self.sheet_path):
            df = pd.DataFrame(columns=["timestamp", "student_id", "scenario", "status", "summary"])
            df.to_csv(self.sheet_path, index=False)

    def load_db(self):
        with open(self.db_path, "r") as f:
            self.db = json.load(f)

    def save_db(self):
        with open(self.db_path, "w") as f:
            json.dump(self.db, f, indent=4)

    def get_student_context(self, student_id):
        student = self.db["students"].get(student_id)
        if not student: return None
        course_info = self.db["courses"].get(student["course"], {})
        
        context = f"Student Name: {student['name']}\nCourse: {student['course']}\n"
        context += f"Attendance: {student['attendance']['history']}\n"
        context += f"Missing Homework: {', '.join(student['homework']['missing_tasks']) if student['homework']['missing_tasks'] else 'None'}\n"
        return context

    async def generate_reply(self, student_id, user_message=None, scenario=None):
        if student_id not in self.chats:
            context = self.get_student_context(student_id)
            system_prompt = f"""You are a helpful teaching assistant reaching out to a student on Telegram.
Scenario: {scenario}
Context: {context}

INSTRUCTIONS:
1. Ground messages only in context. Keep it conversational.
2. If resolved or escalated, append [RESOLVED] or [ESCALATED] at the end of the final message."""
            
            self.chats[student_id] = {
                "scenario": scenario,
                "history": [{"role": "system", "content": system_prompt}]
            }
            initial_prompt = f"Write the initial outreach message for scenario: {scenario}."
            self.chats[student_id]["history"].append({"role": "user", "content": initial_prompt})
        else:
            if user_message is None:
                new_prompt = f"Write another outreach message for a new scenario: {scenario}."
                self.chats[student_id]["history"].append({"role": "user", "content": new_prompt})
            else:
                self.chats[student_id]["history"].append({"role": "user", "content": user_message})

        chat_session = self.chats[student_id]
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=chat_session["history"]
            )
            reply = response.choices[0].message.content
            chat_session["history"].append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"Error connecting to LLM: {str(e)}"

    def _close_interaction(self, student_id, status):
        chat_session = self.chats[student_id]
        scenario = chat_session["scenario"]
        history_text = "\n".join([msg['content'] for msg in chat_session["history"] if msg['role'] != 'system'])
        
        try:
            summary_prompt = f"Summarize this interaction in one sentence. Status: {status}\n\n{history_text}"
            res = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": summary_prompt}]
            )
            summary = res.choices[0].message.content.strip()
        except:
            summary = "Summary generation failed."

        new_row = {"timestamp": datetime.now().isoformat(), "student_id": student_id, "scenario": scenario, "status": status, "summary": summary}
        pd.DataFrame([new_row]).to_csv(self.sheet_path, mode='a', header=False, index=False)
        del self.chats[student_id]

# --- Bot Handlers ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "Hello! I am the Student Agent Bot.\n"
        "To test proactive messaging, you must first link your Telegram account to a mock student ID.\n\n"
        "Use: `/register <student_id>`\n"
        "Example: `/register student_01` (Alice - who is absent)\n"
        "Example: `/register student_02` (Bob - missing homework)\n\n"
        "Once registered, use `/test_schedule` to trigger the daily checks."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data["agent"]
    args = context.args
    if not args:
        await update.message.reply_text("Please provide a student ID. Example: `/register student_01`", parse_mode="Markdown")
        return
        
    student_id = args[0]
    if student_id not in agent.db["students"]:
        await update.message.reply_text(f"Student '{student_id}' not found in mock_db.json.")
        return
        
    chat_id = update.message.chat_id
    
    # Save the real chat ID to the DB so the scheduler knows where to send
    agent.db["students"][student_id]["registered_chat_id"] = chat_id
    agent.save_db()
    
    await update.message.reply_text(f"Successfully linked this chat to {agent.db['students'][student_id]['name']} ({student_id}).")

async def test_schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Triggering all scheduled jobs immediately for registered students...")
    await run_all_tasks(context)

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent = context.bot_data["agent"]
    chat_id = update.message.chat_id
    user_text = update.message.text
    
    # Find which student_id matches this chat_id
    student_id = None
    for sid, data in agent.db["students"].items():
        if data.get("registered_chat_id") == chat_id:
            student_id = sid
            break
            
    if not student_id or student_id not in agent.chats:
        # Ignore messages if not part of an active simulation
        return
        
    reply = await agent.generate_reply(student_id, user_message=user_text)
    
    # Check termination
    if "[RESOLVED]" in reply or "[ESCALATED]" in reply:
        status = "ESCALATED" if "[ESCALATED]" in reply else "RESOLVED"
        clean_reply = reply.replace("[RESOLVED]", "").replace("[ESCALATED]", "").strip()
        await update.message.reply_text(f"🤖 {clean_reply}")
        agent._close_interaction(student_id, status)
        await update.message.reply_text("*(System: Conversation logged to CSV and closed)*", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"🤖 {reply}")

# --- Scheduled Jobs ---

async def proactive_outreach(context: ContextTypes.DEFAULT_TYPE, student_id: str, scenario: str, chat_id: int):
    agent = context.bot_data["agent"]
    reply = await agent.generate_reply(student_id, scenario=scenario)
    try:
        await context.bot.send_message(chat_id=chat_id, text=f"🤖 {reply}")
        logging.info(f"Sent proactive message to {student_id}")
    except Exception as e:
        logging.error(f"Failed to send message to {student_id}: {e}")

async def run_all_tasks(context: ContextTypes.DEFAULT_TYPE):
    """Function to run all 4 tasks for demonstration purposes"""
    agent = context.bot_data["agent"]
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    for sid, data in agent.db["students"].items():
        chat_id = data.get("registered_chat_id")
        if not chat_id:
            continue # Skip unregistered students
            
        # 1. Attendance Check
        if data["attendance"].get("absent_yesterday"):
            await proactive_outreach(context, sid, "Follow up on absence from yesterday's class", chat_id)
            
        # 2. Homework Check
        if data["homework"]["missing_tasks"]:
            await proactive_outreach(context, sid, "Follow up on incomplete homework tasks", chat_id)
            
        # 3. Upcoming Reminders
        course_info = agent.db["courses"].get(data["course"], {})
        upcoming = []
        for session in course_info.get("sessions", []):
            if session["date"] == tomorrow: upcoming.append(f"Session: {session['topic']}")
        for task in course_info.get("tasks", []):
            if task["deadline"] == tomorrow: upcoming.append(f"Deadline: {task['name']}")
                
        if upcoming:
            scenario = f"Remind about upcoming items tomorrow: {', '.join(upcoming)}"
            await proactive_outreach(context, sid, scenario, chat_id)
            
        # 4. Weekly Feedback (run for all registered)
        await proactive_outreach(context, sid, "Weekly check-in: collect course feedback and check preparation", chat_id)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set.")
        return

    agent = ScheduledAgent()
    application = Application.builder().token(token).build()
    application.bot_data["agent"] = agent

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("register", register_cmd))
    application.add_handler(CommandHandler("test_schedule", test_schedule_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))

    # Real-world scheduling would look like this using python-telegram-bot's JobQueue
    # application.job_queue.run_daily(task_attendance, time=time(8, 0)) # Runs at 8 AM daily
    # application.job_queue.run_repeating(task_weekly, interval=604800) # Runs weekly

    print("Scheduled Bot started. Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()

import os
import json
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from openai import OpenAI

class TelethonAgent:
    def __init__(self, db_path="mock_db.json", sheet_path="tracking_sheet.csv"):
        self.db_path = db_path
        self.sheet_path = sheet_path
        
        # Load API keys
        self.api_id = os.environ.get("TELEGRAM_API_ID")
        self.api_hash = os.environ.get("TELEGRAM_API_HASH")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        
        if not self.api_id or not self.api_hash:
            print("ERROR: TELEGRAM_API_ID or TELEGRAM_API_HASH not set. Telethon requires these to act as your user account.")
            # We will still instantiate to show the code, but it will fail on connect
        
        self.client = TelegramClient('my_personal_account', self.api_id, self.api_hash)
        self.llm_client = OpenAI(api_key=self.openai_key)
        self.model_name = "gpt-4o-mini"
        
        self.load_db()
        self.chats = {} # Track active conversations
        
        if not os.path.exists(self.sheet_path):
            df = pd.DataFrame(columns=["timestamp", "student_id", "scenario", "status", "summary"])
            df.to_csv(self.sheet_path, index=False)

    def load_db(self):
        with open(self.db_path, "r") as f:
            self.db = json.load(f)

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
            # Start new chat
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

    async def _close_interaction(self, student_id, status):
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

    async def handle_incoming_message(self, event):
        """Telethon Event Handler for incoming messages."""
        if event.is_group: return # Only handle direct messages
        
        sender = await event.get_sender()
        sender_username = sender.username
        
        # Match username to student in mock_db
        # In a real app, you'd match by phone number or actual User ID.
        matched_student_id = None
        for sid, sdata in self.db["students"].items():
            if sdata["telegram_handle"].replace("@", "") == sender_username:
                matched_student_id = sid
                break
                
        if not matched_student_id or matched_student_id not in self.chats:
            return # Ignore random messages if no active simulation
            
        user_text = event.raw_text
        reply = await self.generate_reply(matched_student_id, user_message=user_text)
        
        # Check termination
        if "[RESOLVED]" in reply or "[ESCALATED]" in reply:
            status = "ESCALATED" if "[ESCALATED]" in reply else "RESOLVED"
            clean_reply = reply.replace("[RESOLVED]", "").replace("[ESCALATED]", "").strip()
            await event.reply(clean_reply)
            await self._close_interaction(matched_student_id, status)
        else:
            await event.reply(reply)

    async def proactive_outreach(self, student_id, scenario):
        """Generates the initial message and sends it via Telethon."""
        print(f"--> Initiating outreach for {student_id} regarding '{scenario}'...")
        reply = await self.generate_reply(student_id, scenario=scenario)
        
        handle = self.db["students"][student_id]["telegram_handle"]
        
        # NOTE: For testing purposes, we override the destination to "me" (Saved Messages)
        # so you don't spam fake accounts and get banned. 
        # In production, change 'me' to the 'handle'.
        target_entity = 'me' # Change to `handle` in production
        
        try:
            await self.client.send_message(target_entity, f"[To {handle}]:\n{reply}")
            print(f"Sent message to {handle} (redirected to Saved Messages for safety)")
        except Exception as e:
            print(f"Failed to send to {handle}: {e}")

    # ================= PERIODIC TASKS =================

    async def task_check_attendance(self):
        """1. Daily: check attendance and message absent students."""
        for sid, data in self.db["students"].items():
            if data["attendance"].get("absent_yesterday"):
                await self.proactive_outreach(sid, "Follow up on absence from yesterday's class")
                await asyncio.sleep(2) # Anti-spam delay

    async def task_weekly_feedback(self):
        """2. Weekly: course feedback and preparation update."""
        for sid, data in self.db["students"].items():
            await self.proactive_outreach(sid, "Weekly check-in: collect course feedback and check preparation")
            await asyncio.sleep(2)

    async def task_check_homework(self):
        """3. Daily: chat with students who didn't complete homework."""
        for sid, data in self.db["students"].items():
            if data["homework"]["missing_tasks"]:
                await self.proactive_outreach(sid, "Follow up on incomplete homework tasks")
                await asyncio.sleep(2)

    async def task_remind_upcoming(self):
        """4. Daily: remind about upcoming task or session tomorrow."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        for sid, data in self.db["students"].items():
            course_info = self.db["courses"].get(data["course"], {})
            
            # Find sessions or tasks for tomorrow
            upcoming = []
            for session in course_info.get("sessions", []):
                if session["date"] == tomorrow:
                    upcoming.append(f"Session: {session['topic']}")
            for task in course_info.get("tasks", []):
                if task["deadline"] == tomorrow:
                    upcoming.append(f"Deadline: {task['name']}")
                    
            if upcoming:
                scenario = f"Remind about upcoming items tomorrow: {', '.join(upcoming)}"
                await self.proactive_outreach(sid, scenario)
                await asyncio.sleep(2)

    async def run_scheduler_test_mode(self):
        """Run all tasks immediately for demonstration purposes."""
        print("\n--- RUNNING SCHEDULER TEST MODE ---")
        print("1. Checking Attendance...")
        await self.task_check_attendance()
        
        print("\n2. Checking Homework...")
        await self.task_check_homework()
        
        print("\n3. Checking Upcoming Reminders...")
        await self.task_remind_upcoming()
        
        print("\n4. Running Weekly Feedback... (Skipping full loop in test to save API calls)")
        # Just test one student for the weekly feedback to save OpenAI calls
        await self.proactive_outreach("student_04", "Weekly check-in: collect course feedback and check preparation")
        print("--- SCHEDULER TEST COMPLETE ---\n")

async def main():
    agent = TelethonAgent()
    
    # Register the event handler
    agent.client.add_event_handler(agent.handle_incoming_message, events.NewMessage(incoming=True))
    
    print("Starting Telethon Client...")
    await agent.client.start()
    
    # Run the scheduled tasks once immediately for the demo
    await agent.run_scheduler_test_mode()
    
    print("Agent is now listening for replies in the background. Press Ctrl+C to stop.")
    await agent.client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())

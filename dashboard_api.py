"""
dashboard_api.py
FastAPI backend serving CSV data for the dashboard UI.
Also provides endpoints to mark attendance, update homework, and trigger outreach.
"""

from dotenv import load_dotenv
load_dotenv()
import os
import logging
import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from data_manager import DataManager
from agent import StudentAgent
from bot import cmd_start, cmd_register, cmd_trigger, cmd_status, handle_message
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from contextlib import asynccontextmanager

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize and start the Telegram Bot
    ptb_app = Application.builder().token(BOT_TOKEN).build()
    ptb_app.bot_data["data_manager"] = dm
    ptb_app.bot_data["agent"] = agent

    ptb_app.add_handler(CommandHandler("start", cmd_start))
    ptb_app.add_handler(CommandHandler("register", cmd_register))
    ptb_app.add_handler(CommandHandler("trigger", cmd_trigger))
    ptb_app.add_handler(CommandHandler("status", cmd_status))
    ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await ptb_app.initialize()
    await ptb_app.start()
    await ptb_app.updater.start_polling()
    
    app_state["ptb_app"] = ptb_app
    yield
    
    # Shutdown the Telegram Bot
    await ptb_app.updater.stop()
    await ptb_app.stop()
    await ptb_app.shutdown()

app = FastAPI(title="Student Outreach Dashboard", lifespan=lifespan)

dm = DataManager()
agent = StudentAgent(data_manager=dm)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


# ── Pydantic models ──────────────────────────────────────────

class AttendanceMark(BaseModel):
    student_id: str
    session_id: str
    status: str  # "Present" or "Absent"


class HomeworkMark(BaseModel):
    student_id: str
    assignment_id: str
    status: str  # "Complete", "Incomplete", or "Pending"


class TriggerRequest(BaseModel):
    task: str  # "attendance", "homework", "reminders", "feedback", "all"


# ── API: Students ────────────────────────────────────────────

@app.get("/api/students")
def get_students(course_id: str = ""):
    dm.reload()
    df = dm.students
    if course_id:
        df = df[df["course_id"] == course_id]
    students = df.to_dict(orient="records")
    for s in students:
        s["course_name"] = dm.get_course_name(s["course_id"])
        s["attendance_summary"] = dm.get_attendance_summary(s["student_id"])
    return students


@app.get("/api/courses")
def get_courses():
    dm.reload()
    return dm.courses.to_dict(orient="records")


# ── API: Attendance ──────────────────────────────────────────

@app.get("/api/sessions")
def get_sessions():
    dm.reload()
    sessions = dm.sessions.merge(dm.courses, on="course_id", how="left")
    return sessions.to_dict(orient="records")


@app.get("/api/attendance")
def get_attendance(session_id: str = "", course_id: str = "", date: str = ""):
    dm.reload()
    records = dm.attendance
    if session_id:
        records = records[records["session_id"] == session_id]
    if course_id or date:
        session_filter = dm.sessions.copy()
        if course_id:
            session_filter = session_filter[session_filter["course_id"] == course_id]
        if date:
            session_filter = session_filter[session_filter["date"] == date]
        valid_session_ids = session_filter["session_id"].tolist()
        records = records[records["session_id"].isin(valid_session_ids)]
    merged = records.merge(dm.students[["student_id", "name"]], on="student_id", how="left")
    merged = merged.merge(dm.sessions[["session_id", "date", "topic", "course_id"]], on="session_id", how="left")
    merged = merged.merge(dm.courses, on="course_id", how="left")
    return merged.fillna("").to_dict(orient="records")


@app.get("/api/attendance/dates")
def get_attendance_dates(course_id: str = ""):
    """Return distinct session dates, optionally filtered by course."""
    dm.reload()
    sessions = dm.sessions
    if course_id:
        sessions = sessions[sessions["course_id"] == course_id]
    sessions = sessions.merge(dm.courses, on="course_id", how="left")
    return sessions[["session_id", "date", "topic", "course_id", "course_name"]].to_dict(orient="records")


@app.get("/api/attendance/summary")
def get_attendance_summary(course_id: str = ""):
    """Per-student attendance stats, optionally filtered by course."""
    dm.reload()
    students = dm.students
    if course_id:
        students = students[students["course_id"] == course_id]
    results = []
    for _, stu in students.iterrows():
        records = dm.attendance[dm.attendance["student_id"] == stu["student_id"]]
        total = len(records)
        present = len(records[records["status"] == "Present"])
        absent = total - present
        pct = round((present / total) * 100, 1) if total > 0 else 0
        results.append({
            "student_id": stu["student_id"],
            "name": stu["name"],
            "course_id": stu["course_id"],
            "course_name": dm.get_course_name(stu["course_id"]),
            "total_sessions": total,
            "present": present,
            "absent": absent,
            "percentage": pct,
        })
    return results


@app.post("/api/attendance/mark")
def mark_attendance(payload: AttendanceMark):
    dm.reload()
    mask = (dm.attendance["student_id"] == payload.student_id) & \
           (dm.attendance["session_id"] == payload.session_id)
    if mask.any():
        dm.attendance.loc[mask, "status"] = payload.status
    else:
        import pandas as pd
        new_row = pd.DataFrame([{
            "student_id": payload.student_id,
            "session_id": payload.session_id,
            "status": payload.status,
        }])
        dm.attendance = pd.concat([dm.attendance, new_row], ignore_index=True)
    dm.save_attendance()
    return {"message": f"Marked {payload.student_id} as {payload.status} for {payload.session_id}"}


# ── API: Homework / Assignments ──────────────────────────────

@app.get("/api/assignments")
def get_assignments():
    dm.reload()
    merged = dm.assignments.merge(dm.courses, on="course_id", how="left")
    return merged.fillna("").to_dict(orient="records")


@app.get("/api/homework")
def get_homework(assignment_id: str = "", student_id: str = "", course_id: str = ""):
    dm.reload()
    sa = dm.student_assignments
    if assignment_id:
        sa = sa[sa["assignment_id"] == assignment_id]
    if student_id:
        sa = sa[sa["student_id"] == student_id]
    # Join student info
    merged = sa.merge(dm.students[["student_id", "name", "course_id"]], on="student_id", how="left")
    merged = merged.rename(columns={"name": "student_name", "course_id": "student_course_id"})
    # Join assignment info
    merged = merged.merge(dm.assignments, on="assignment_id", how="left")
    merged = merged.rename(columns={"name": "assignment_name"})
    # Join course info
    merged = merged.merge(dm.courses, on="course_id", how="left")
    # Filter by course
    if course_id:
        merged = merged[merged["course_id"] == course_id]
    return merged.fillna("").to_dict(orient="records")


@app.post("/api/homework/mark")
def mark_homework(payload: HomeworkMark):
    dm.reload()
    mask = (dm.student_assignments["student_id"] == payload.student_id) & \
           (dm.student_assignments["assignment_id"] == payload.assignment_id)
    if mask.any():
        dm.student_assignments.loc[mask, "status"] = payload.status
        dm.save_student_assignments()
        return {"message": f"Updated {payload.student_id} → {payload.assignment_id} to {payload.status}"}
    raise HTTPException(status_code=404, detail="Record not found")


# ── API: Upcoming ────────────────────────────────────────────

@app.get("/api/upcoming")
def get_upcoming():
    dm.reload()
    today = datetime.now().strftime("%Y-%m-%d")
    future_sessions = dm.sessions[dm.sessions["date"] >= today].copy()
    future_sessions = future_sessions.merge(dm.courses, on="course_id", how="left")
    future_sessions["type"] = "Session"
    future_sessions = future_sessions.rename(columns={"topic": "detail", "date": "event_date"})

    future_assignments = dm.assignments[dm.assignments["deadline"] >= today].copy()
    future_assignments = future_assignments.merge(dm.courses, on="course_id", how="left")
    future_assignments["type"] = "Deadline"
    future_assignments = future_assignments.rename(columns={"name": "detail", "deadline": "event_date"})

    import pandas as pd
    combined = pd.concat([
        future_sessions[["event_date", "type", "detail", "course_name", "course_id"]],
        future_assignments[["event_date", "type", "detail", "course_name", "course_id"]],
    ], ignore_index=True).sort_values("event_date")

    return combined.fillna("").to_dict(orient="records")


# ── API: Interaction Logs ────────────────────────────────────

@app.get("/api/logs")
def get_interaction_logs():
    dm.reload()
    log_path = os.path.join(dm.data_dir, "interaction_logs.csv")
    import pandas as pd
    try:
        logs = pd.read_csv(log_path, dtype=str).fillna("")
        return logs.sort_values("timestamp", ascending=False).to_dict(orient="records")
    except Exception:
        return []


# ── API: Trigger Outreach ────────────────────────────────────

async def _send_telegram(chat_id: str, text: str):
    """Send a message via the Telegram Bot API."""
    ptb_app = app_state.get("ptb_app")
    if not ptb_app:
        logger.warning("Bot is not running. Skipping Telegram send.")
        return False
    try:
        await ptb_app.bot.send_message(chat_id=int(chat_id), text=text)
        return True
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False


@app.post("/api/trigger")
async def trigger_outreach(payload: TriggerRequest):
    dm.reload()
    results = []

    if payload.task in ("attendance", "all"):
        absent = dm.get_absent_yesterday()
        for rec in absent:
            chat_id = (dm.get_student(rec["student_id"]) or {}).get("registered_chat_id", "")
            if not chat_id:
                continue
            course_name = dm.get_course_name(rec["course_id"])
            scenario = f"Follow up on absence from yesterday's {course_name} session on '{rec['topic']}'"
            reply = agent.start_conversation(rec["student_id"], scenario)
            sent = await _send_telegram(chat_id, reply)
            results.append({"student_id": rec["student_id"], "scenario": scenario, "sent": sent})

    if payload.task in ("homework", "all"):
        incomplete = dm.get_incomplete_assignments()
        for rec in incomplete:
            chat_id = (dm.get_student(rec["student_id"]) or {}).get("registered_chat_id", "")
            if not chat_id:
                continue
            course_name = dm.get_course_name(rec["course_id"])
            scenario = f"Follow up on incomplete assignment '{rec['assignment_name']}' in {course_name}"
            reply = agent.start_conversation(rec["student_id"], scenario)
            sent = await _send_telegram(chat_id, reply)
            results.append({"student_id": rec["student_id"], "scenario": scenario, "sent": sent})

    if payload.task in ("reminders", "all"):
        upcoming = dm.get_upcoming_tomorrow()
        grouped: dict[str, list[str]] = {}
        course_map: dict[str, str] = {}
        for item in upcoming:
            sid = item["student_id"]
            grouped.setdefault(sid, []).append(item["detail"])
            course_map[sid] = item["course_id"]
        for sid, details in grouped.items():
            chat_id = (dm.get_student(sid) or {}).get("registered_chat_id", "")
            if not chat_id:
                continue
            course_name = dm.get_course_name(course_map[sid])
            scenario = f"Remind about tomorrow's items in {course_name}: {'; '.join(details)}"
            reply = agent.start_conversation(sid, scenario)
            sent = await _send_telegram(chat_id, reply)
            results.append({"student_id": sid, "scenario": scenario, "sent": sent})

    if payload.task in ("feedback", "all"):
        registered = dm.get_registered_students()
        for _, stu in registered.iterrows():
            course_name = dm.get_course_name(stu["course_id"])
            scenario = f"Weekly check-in for {course_name}: gather course satisfaction feedback"
            reply = agent.start_conversation(stu["student_id"], scenario)
            sent = await _send_telegram(stu["registered_chat_id"], reply)
            results.append({"student_id": stu["student_id"], "scenario": scenario, "sent": sent})

    return {"triggered": len(results), "results": results}


# ── Serve the frontend ───────────────────────────────────────

os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse(os.path.join("static", "index.html"))

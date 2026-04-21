"""
scheduler.py
Contains the four periodic outreach tasks that scan the data layer
and push messages to students via the Telegram bot.
"""

import logging
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def send_outreach(context: ContextTypes.DEFAULT_TYPE, student_id: str,
                        chat_id: str, scenario: str):
    """Generate an LLM message and send it to the student's Telegram chat."""
    agent = context.bot_data["agent"]
    reply = agent.start_conversation(student_id, scenario)
    try:
        await context.bot.send_message(chat_id=int(chat_id), text=reply)
        logger.info("Outreach sent → %s | %s", student_id, scenario)
    except Exception as e:
        logger.error("Failed to send to %s (chat %s): %s", student_id, chat_id, e)


def _registered_only(dm, student_id: str) -> str | None:
    """Return the chat_id if the student is registered, else None."""
    stu = dm.get_student(student_id)
    if stu and stu.get("registered_chat_id"):
        return stu["registered_chat_id"]
    return None


# ── Task 1: Daily attendance check ──────────────────────────

async def task_attendance(context: ContextTypes.DEFAULT_TYPE):
    """Check yesterday's attendance and message absent students."""
    dm = context.bot_data["data_manager"]
    dm.reload()
    absent_list = dm.get_absent_yesterday()

    if not absent_list:
        logger.info("Attendance check: no absences found for yesterday.")
        return

    for record in absent_list:
        chat_id = _registered_only(dm, record["student_id"])
        if not chat_id:
            continue
        course_name = dm.get_course_name(record["course_id"])
        scenario = (
            f"Follow up on absence from yesterday's {course_name} session "
            f"on '{record['topic']}'"
        )
        await send_outreach(context, record["student_id"], chat_id, scenario)


# ── Task 2: Weekly feedback & preparation ────────────────────

async def task_weekly_feedback(context: ContextTypes.DEFAULT_TYPE):
    """Reach out to all registered students for course feedback."""
    dm = context.bot_data["data_manager"]
    dm.reload()
    registered = dm.get_registered_students()

    for _, stu in registered.iterrows():
        course_name = dm.get_course_name(stu["course_id"])
        scenario = (
            f"Weekly check-in for {course_name}: gather course satisfaction "
            f"feedback and ask about preparation for upcoming sessions"
        )
        await send_outreach(context, stu["student_id"], stu["registered_chat_id"], scenario)


# ── Task 3: Daily homework follow-up ────────────────────────

async def task_homework(context: ContextTypes.DEFAULT_TYPE):
    """Message students with incomplete, overdue assignments."""
    dm = context.bot_data["data_manager"]
    dm.reload()
    incomplete = dm.get_incomplete_assignments()

    if not incomplete:
        logger.info("Homework check: no incomplete assignments found.")
        return

    for record in incomplete:
        chat_id = _registered_only(dm, record["student_id"])
        if not chat_id:
            continue
        course_name = dm.get_course_name(record["course_id"])
        scenario = (
            f"Follow up on incomplete assignment '{record['assignment_name']}' "
            f"in {course_name} (was due {record['deadline']})"
        )
        await send_outreach(context, record["student_id"], chat_id, scenario)


# ── Task 4: Daily upcoming reminders ────────────────────────

async def task_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Remind students about sessions and deadlines scheduled for tomorrow."""
    dm = context.bot_data["data_manager"]
    dm.reload()
    upcoming = dm.get_upcoming_tomorrow()

    if not upcoming:
        logger.info("Reminder check: nothing scheduled for tomorrow.")
        return

    # Group by student so each student gets one consolidated message
    grouped: dict[str, list[str]] = {}
    course_map: dict[str, str] = {}
    for item in upcoming:
        sid = item["student_id"]
        grouped.setdefault(sid, []).append(item["detail"])
        course_map[sid] = item["course_id"]

    for sid, details in grouped.items():
        chat_id = _registered_only(dm, sid)
        if not chat_id:
            continue
        course_name = dm.get_course_name(course_map[sid])
        items_text = "; ".join(details)
        scenario = f"Remind about tomorrow's items in {course_name}: {items_text}"
        await send_outreach(context, sid, chat_id, scenario)


# ── Combined runner (for /trigger command) ───────────────────

async def run_all_tasks(context: ContextTypes.DEFAULT_TYPE):
    """Execute all four scheduled tasks immediately."""
    logger.info("── Running all scheduled tasks ──")
    await task_attendance(context)
    await task_homework(context)
    await task_reminders(context)
    await task_weekly_feedback(context)
    logger.info("── All scheduled tasks complete ──")

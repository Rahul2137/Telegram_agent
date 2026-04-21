"""
data_manager.py
Centralized data access layer. Reads, queries, and updates the relational CSV files.
"""

import os
import pandas as pd
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class DataManager:
    """Provides structured access to the CSV-based data layer."""

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.reload()

    def reload(self):
        """Reload all CSV files from disk into memory."""
        self.students = pd.read_csv(os.path.join(self.data_dir, "students.csv"), dtype=str).fillna("")
        self.courses = pd.read_csv(os.path.join(self.data_dir, "courses.csv"), dtype=str).fillna("")
        self.sessions = pd.read_csv(os.path.join(self.data_dir, "sessions.csv"), dtype=str).fillna("")
        self.assignments = pd.read_csv(os.path.join(self.data_dir, "assignments.csv"), dtype=str).fillna("")
        self.attendance = pd.read_csv(os.path.join(self.data_dir, "attendance.csv"), dtype=str).fillna("")
        self.student_assignments = pd.read_csv(os.path.join(self.data_dir, "student_assignments.csv"), dtype=str).fillna("")

    # ── Save helpers ─────────────────────────────────────────

    def save_students(self):
        self.students.to_csv(os.path.join(self.data_dir, "students.csv"), index=False)

    def save_attendance(self):
        self.attendance.to_csv(os.path.join(self.data_dir, "attendance.csv"), index=False)

    def save_student_assignments(self):
        self.student_assignments.to_csv(os.path.join(self.data_dir, "student_assignments.csv"), index=False)

    # ── Student queries ──────────────────────────────────────

    def get_student(self, student_id: str) -> dict | None:
        row = self.students[self.students["student_id"] == student_id]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def get_student_by_chat_id(self, chat_id: str) -> dict | None:
        row = self.students[self.students["registered_chat_id"] == str(chat_id)]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def register_chat_id(self, student_id: str, chat_id: int):
        """Link a Telegram chat ID to a student record."""
        idx = self.students.index[self.students["student_id"] == student_id]
        if not idx.empty:
            self.students.loc[idx, "registered_chat_id"] = str(chat_id)
            self.save_students()

    def get_registered_students(self) -> pd.DataFrame:
        """Return students that have a registered Telegram chat ID."""
        return self.students[self.students["registered_chat_id"] != ""]

    # ── Course queries ───────────────────────────────────────

    def get_course_name(self, course_id: str) -> str:
        row = self.courses[self.courses["course_id"] == course_id]
        return row.iloc[0]["course_name"] if not row.empty else course_id

    # ── Attendance queries ───────────────────────────────────

    def get_absent_yesterday(self) -> list[dict]:
        """Return list of {student_id, session_id, topic} for students absent yesterday."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_sessions = self.sessions[self.sessions["date"] == yesterday]
        if yesterday_sessions.empty:
            return []

        results = []
        for _, sess in yesterday_sessions.iterrows():
            absent = self.attendance[
                (self.attendance["session_id"] == sess["session_id"]) &
                (self.attendance["status"] == "Absent")
            ]
            for _, att in absent.iterrows():
                results.append({
                    "student_id": att["student_id"],
                    "session_id": sess["session_id"],
                    "topic": sess["topic"],
                    "course_id": sess["course_id"],
                })
        return results

    def get_attendance_summary(self, student_id: str) -> str:
        """Return a human-readable attendance summary for a student."""
        records = self.attendance[self.attendance["student_id"] == student_id]
        total = len(records)
        present = len(records[records["status"] == "Present"])
        return f"Attended {present}/{total} sessions"

    # ── Assignment queries ───────────────────────────────────

    def get_incomplete_assignments(self) -> list[dict]:
        """Return list of {student_id, assignment_name, deadline} for overdue incomplete work."""
        today = datetime.now().strftime("%Y-%m-%d")
        overdue = self.assignments[self.assignments["deadline"] <= today]
        results = []
        for _, assign in overdue.iterrows():
            incomplete = self.student_assignments[
                (self.student_assignments["assignment_id"] == assign["assignment_id"]) &
                (self.student_assignments["status"] == "Incomplete")
            ]
            for _, sa in incomplete.iterrows():
                results.append({
                    "student_id": sa["student_id"],
                    "assignment_id": assign["assignment_id"],
                    "assignment_name": assign["name"],
                    "deadline": assign["deadline"],
                    "course_id": assign["course_id"],
                })
        return results

    def get_assignment_summary(self, student_id: str) -> str:
        """Return human-readable assignment status for a student."""
        records = self.student_assignments[self.student_assignments["student_id"] == student_id]
        merged = records.merge(self.assignments, on="assignment_id", how="left")
        lines = []
        for _, r in merged.iterrows():
            lines.append(f"  - {r['name']} (deadline: {r['deadline']}): {r['status']}")
        return "\n".join(lines) if lines else "  No assignments found."

    # ── Upcoming events ──────────────────────────────────────

    def get_upcoming_tomorrow(self) -> list[dict]:
        """Return sessions and assignment deadlines scheduled for tomorrow."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        results = []

        for _, sess in self.sessions[self.sessions["date"] == tomorrow].iterrows():
            enrolled = self.students[self.students["course_id"] == sess["course_id"]]
            for _, stu in enrolled.iterrows():
                results.append({
                    "student_id": stu["student_id"],
                    "type": "session",
                    "detail": f"Session: {sess['topic']}",
                    "course_id": sess["course_id"],
                })

        for _, assign in self.assignments[self.assignments["deadline"] == tomorrow].iterrows():
            enrolled = self.students[self.students["course_id"] == assign["course_id"]]
            for _, stu in enrolled.iterrows():
                results.append({
                    "student_id": stu["student_id"],
                    "type": "deadline",
                    "detail": f"Assignment Due: {assign['name']}",
                    "course_id": assign["course_id"],
                })
        return results

    # ── Interaction logging ──────────────────────────────────

    def log_interaction(self, student_id: str, scenario: str, status: str, summary: str):
        """Append a row to interaction_logs.csv."""
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().isoformat(),
            "student_id": student_id,
            "scenario": scenario,
            "status": status,
            "summary": summary,
        }])
        log_path = os.path.join(self.data_dir, "interaction_logs.csv")
        new_row.to_csv(log_path, mode="a", header=False, index=False)

    # ── Context builder ──────────────────────────────────────

    def build_student_context(self, student_id: str) -> str | None:
        """Build a full text context block for a student for LLM grounding."""
        student = self.get_student(student_id)
        if not student:
            return None

        course_name = self.get_course_name(student["course_id"])
        attendance = self.get_attendance_summary(student_id)
        assignments = self.get_assignment_summary(student_id)

        context = (
            f"Student: {student['name']} ({student_id})\n"
            f"Course: {course_name}\n"
            f"Status: {student['status']}\n"
            f"Attendance: {attendance}\n"
            f"Assignments:\n{assignments}\n"
        )
        if student.get("teacher_notes"):
            context += f"Teacher Notes: {student['teacher_notes']}\n"
        return context

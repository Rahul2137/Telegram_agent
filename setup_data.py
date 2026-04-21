"""
setup_data.py
Generates the relational CSV data files with realistic sample data.
Run once to initialize the data layer.
"""

import pandas as pd
from datetime import datetime, timedelta
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def generate_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # ── Courses ──────────────────────────────────────────────
    courses = pd.DataFrame([
        {"course_id": "CS101", "course_name": "Intro to Data Science"},
        {"course_id": "CS201", "course_name": "Advanced AI"},
        {"course_id": "CS301", "course_name": "Web Development"},
        {"course_id": "CS401", "course_name": "Cloud Computing"},
    ])
    courses.to_csv(os.path.join(DATA_DIR, "courses.csv"), index=False)

    # ── Sessions (8 per course) ──────────────────────────────
    session_rows = []
    for cid in courses["course_id"]:
        base = today - timedelta(days=14)
        topics = {
            "CS101": ["Python Basics", "Pandas & DataFrames", "Data Cleaning",
                       "Exploratory Analysis", "Intro to ML", "Linear Regression",
                       "Model Evaluation", "Final Review"],
            "CS201": ["Deep Learning Basics", "Neural Networks", "CNNs", "RNNs",
                       "Transformers", "GANs", "Reinforcement Learning", "Deployment"],
            "CS301": ["HTML & CSS", "JavaScript Basics", "React Components",
                       "React State", "Node.js Basics", "Express & APIs",
                       "Databases", "Fullstack Integration"],
            "CS401": ["Cloud Fundamentals", "AWS Overview", "Docker Basics",
                       "Kubernetes", "CI/CD Pipelines", "Serverless",
                       "Monitoring", "Capstone Workshop"],
        }
        for idx in range(8):
            session_date = base + timedelta(days=idx * 3)
            session_rows.append({
                "session_id": f"{cid}_S{idx+1}",
                "course_id": cid,
                "date": session_date.strftime("%Y-%m-%d"),
                "topic": topics[cid][idx],
            })
    sessions = pd.DataFrame(session_rows)
    sessions.to_csv(os.path.join(DATA_DIR, "sessions.csv"), index=False)

    # ── Assignments (3-4 per course) ─────────────────────────
    assignment_rows = []
    assign_meta = {
        "CS101": [("Homework 1", -7), ("Homework 2", -1), ("Midterm Project", 7), ("Final Project", 35)],
        "CS201": [("Assignment 1", -7), ("Assignment 2", 1), ("Kaggle Competition", 7)],
        "CS301": [("Portfolio Site", -7), ("React App", 1), ("API Service", 7)],
        "CS401": [("Docker Lab", -7), ("CI/CD Pipeline", 1), ("Capstone Proposal", 14)],
    }
    for cid, tasks in assign_meta.items():
        for idx, (name, delta) in enumerate(tasks):
            assignment_rows.append({
                "assignment_id": f"{cid}_A{idx+1}",
                "course_id": cid,
                "name": name,
                "deadline": (today + timedelta(days=delta)).strftime("%Y-%m-%d"),
            })
    assignments = pd.DataFrame(assignment_rows)
    assignments.to_csv(os.path.join(DATA_DIR, "assignments.csv"), index=False)

    # ── Students ─────────────────────────────────────────────
    names = [
        "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank",
        "Grace", "Heidi", "Ivan", "Judy", "Mallory", "Nina",
        "Oscar", "Peggy", "Romeo", "Sybil", "Trent", "Victor",
        "Walter", "Zoe",
    ]
    course_ids = list(courses["course_id"])
    student_rows = []
    for i, name in enumerate(names):
        cid = course_ids[i % len(course_ids)]
        student_rows.append({
            "student_id": f"STU{i+1:03d}",
            "name": name,
            "course_id": cid,
            "telegram_handle": "",
            "registered_chat_id": "",
            "status": "active",
            "teacher_notes": "",
        })
    # Mark a few at-risk
    student_rows[2]["status"] = "at_risk"
    student_rows[2]["teacher_notes"] = "Frequently absent. Needs academic counseling."
    student_rows[10]["status"] = "at_risk"
    student_rows[10]["teacher_notes"] = "Struggling with assignments. Offer extra support."
    student_rows[6]["teacher_notes"] = "Excellent engagement in class."

    students = pd.DataFrame(student_rows)
    students.to_csv(os.path.join(DATA_DIR, "students.csv"), index=False)

    # ── Attendance ───────────────────────────────────────────
    # Generate attendance for past sessions only
    past_sessions = sessions[sessions["date"] <= today.strftime("%Y-%m-%d")]
    attendance_rows = []
    import random
    random.seed(42)
    for _, sess in past_sessions.iterrows():
        enrolled = students[students["course_id"] == sess["course_id"]]
        for _, stu in enrolled.iterrows():
            # ~20% chance absent
            status = "Absent" if random.random() < 0.20 else "Present"
            attendance_rows.append({
                "student_id": stu["student_id"],
                "session_id": sess["session_id"],
                "status": status,
            })
    # Force some absences yesterday for testing
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    yesterday_sessions = sessions[sessions["date"] == yesterday_str]
    for _, sess in yesterday_sessions.iterrows():
        enrolled = students[students["course_id"] == sess["course_id"]]
        for idx, (_, stu) in enumerate(enrolled.iterrows()):
            if idx < 2:  # first 2 enrolled students absent yesterday
                for i, row in enumerate(attendance_rows):
                    if row["student_id"] == stu["student_id"] and row["session_id"] == sess["session_id"]:
                        attendance_rows[i]["status"] = "Absent"

    attendance = pd.DataFrame(attendance_rows)
    attendance.to_csv(os.path.join(DATA_DIR, "attendance.csv"), index=False)

    # ── Student Assignments ──────────────────────────────────
    sa_rows = []
    for _, assign in assignments.iterrows():
        enrolled = students[students["course_id"] == assign["course_id"]]
        for _, stu in enrolled.iterrows():
            if assign["deadline"] <= today.strftime("%Y-%m-%d"):
                status = "Incomplete" if random.random() < 0.25 else "Complete"
            else:
                status = "Pending"
            sa_rows.append({
                "student_id": stu["student_id"],
                "assignment_id": assign["assignment_id"],
                "status": status,
            })
    student_assignments = pd.DataFrame(sa_rows)
    student_assignments.to_csv(os.path.join(DATA_DIR, "student_assignments.csv"), index=False)

    # ── Interaction Logs (empty) ─────────────────────────────
    interaction_logs = pd.DataFrame(columns=[
        "timestamp", "student_id", "scenario", "status", "summary"
    ])
    interaction_logs.to_csv(os.path.join(DATA_DIR, "interaction_logs.csv"), index=False)

    print(f"Data layer initialized in '{DATA_DIR}/' with:")
    print(f"  - {len(courses)} courses")
    print(f"  - {len(sessions)} sessions")
    print(f"  - {len(assignments)} assignments")
    print(f"  - {len(students)} students")
    print(f"  - {len(attendance)} attendance records")
    print(f"  - {len(student_assignments)} student-assignment records")


if __name__ == "__main__":
    generate_data()

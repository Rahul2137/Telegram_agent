import json
from datetime import datetime, timedelta
import random

def generate_db():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    last_week = today - timedelta(days=7)
    next_week = today + timedelta(days=7)

    courses = {
        "Intro to Data Science": {
            "sessions": [
                {"id": "session_1", "date": (last_week - timedelta(days=2)).strftime("%Y-%m-%d"), "topic": "Python Basics"},
                {"id": "session_2", "date": yesterday.strftime("%Y-%m-%d"), "topic": "Pandas & DataFrames"},
                {"id": "session_3", "date": tomorrow.strftime("%Y-%m-%d"), "topic": "Data Cleaning"},
                {"id": "session_4", "date": next_week.strftime("%Y-%m-%d"), "topic": "Intro to ML"},
                {"id": "session_5", "date": (next_week + timedelta(days=7)).strftime("%Y-%m-%d"), "topic": "Linear Regression"},
                {"id": "session_6", "date": (next_week + timedelta(days=14)).strftime("%Y-%m-%d"), "topic": "Logistic Regression"},
                {"id": "session_7", "date": (next_week + timedelta(days=21)).strftime("%Y-%m-%d"), "topic": "Model Evaluation"},
                {"id": "session_8", "date": (next_week + timedelta(days=28)).strftime("%Y-%m-%d"), "topic": "Final Project Overview"},
            ],
            "tasks": [
                {"id": "task_1", "name": "Homework 1", "deadline": last_week.strftime("%Y-%m-%d")},
                {"id": "task_2", "name": "Homework 2", "deadline": yesterday.strftime("%Y-%m-%d")},
                {"id": "task_3", "name": "Midterm Project", "deadline": next_week.strftime("%Y-%m-%d")},
                {"id": "task_4", "name": "Final Project", "deadline": (next_week + timedelta(days=28)).strftime("%Y-%m-%d")},
            ]
        },
        "Advanced AI": {
            "sessions": [
                {"id": "session_1", "date": (last_week - timedelta(days=2)).strftime("%Y-%m-%d"), "topic": "Deep Learning Basics"},
                {"id": "session_2", "date": yesterday.strftime("%Y-%m-%d"), "topic": "Neural Networks"},
                {"id": "session_3", "date": tomorrow.strftime("%Y-%m-%d"), "topic": "CNNs"},
                {"id": "session_4", "date": next_week.strftime("%Y-%m-%d"), "topic": "RNNs"},
                {"id": "session_5", "date": (next_week + timedelta(days=7)).strftime("%Y-%m-%d"), "topic": "Transformers"},
                {"id": "session_6", "date": (next_week + timedelta(days=14)).strftime("%Y-%m-%d"), "topic": "GANs"},
                {"id": "session_7", "date": (next_week + timedelta(days=21)).strftime("%Y-%m-%d"), "topic": "Reinforcement Learning"},
                {"id": "session_8", "date": (next_week + timedelta(days=28)).strftime("%Y-%m-%d"), "topic": "Deployment"},
            ],
            "tasks": [
                {"id": "task_1", "name": "Assignment 1", "deadline": last_week.strftime("%Y-%m-%d")},
                {"id": "task_2", "name": "Assignment 2", "deadline": tomorrow.strftime("%Y-%m-%d")},
                {"id": "task_3", "name": "Kaggle Competition", "deadline": next_week.strftime("%Y-%m-%d")},
            ]
        },
        "Web Development": {
            "sessions": [
                {"id": "session_1", "date": (last_week - timedelta(days=2)).strftime("%Y-%m-%d"), "topic": "HTML & CSS"},
                {"id": "session_2", "date": yesterday.strftime("%Y-%m-%d"), "topic": "JavaScript Basics"},
                {"id": "session_3", "date": tomorrow.strftime("%Y-%m-%d"), "topic": "React Components"},
                {"id": "session_4", "date": next_week.strftime("%Y-%m-%d"), "topic": "React State"},
                {"id": "session_5", "date": (next_week + timedelta(days=7)).strftime("%Y-%m-%d"), "topic": "Node.js Basics"},
                {"id": "session_6", "date": (next_week + timedelta(days=14)).strftime("%Y-%m-%d"), "topic": "Express & APIs"},
                {"id": "session_7", "date": (next_week + timedelta(days=21)).strftime("%Y-%m-%d"), "topic": "Databases"},
                {"id": "session_8", "date": (next_week + timedelta(days=28)).strftime("%Y-%m-%d"), "topic": "Fullstack Integration"},
            ],
            "tasks": [
                {"id": "task_1", "name": "Portfolio Site", "deadline": last_week.strftime("%Y-%m-%d")},
                {"id": "task_2", "name": "React App", "deadline": tomorrow.strftime("%Y-%m-%d")},
                {"id": "task_3", "name": "API Service", "deadline": next_week.strftime("%Y-%m-%d")},
            ]
        }
    }

    first_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Heidi", "Ivan", "Judy", "Mallory", "Nina", "Oscar", "Peggy", "Romeo", "Sybil", "Trent", "Victor", "Walter", "Zoe"]
    course_keys = list(courses.keys())
    
    students = {}
    
    # We will assume a sandbox setup where phone numbers are placeholders.
    # In reality, this would be their telegram handle or phone number registered.
    for i, name in enumerate(first_names):
        student_id = f"student_{i+1:02d}"
        course = random.choice(course_keys)
        
        # Determine attendance for yesterday's session
        # Let's make ~25% absent
        absent_yesterday = random.random() < 0.25
        
        # Determine if they missed a past homework
        # Let's make ~30% have incomplete homework
        missing_homework = []
        if random.random() < 0.30:
            past_tasks = [t for t in courses[course]["tasks"] if t["deadline"] <= today.strftime("%Y-%m-%d")]
            if past_tasks:
                missing_homework.append(random.choice(past_tasks)["name"])

        students[student_id] = {
            "name": name,
            "telegram_handle": f"@{name.lower()}_test", # Placeholder
            "course": course,
            "status": "active" if random.random() < 0.8 else "at_risk",
            "attendance": {
                "absent_yesterday": absent_yesterday,
                "history": f"Attended {random.randint(1, 8)}/8 classes so far."
            },
            "homework": {
                "missing_tasks": missing_homework
            },
            "teacher_notes": "Needs extra help." if missing_homework or absent_yesterday else "Doing well."
        }

    # Ensure we have at least one of each for testing
    # Force Alice to be absent yesterday
    students["student_01"]["attendance"]["absent_yesterday"] = True
    
    # Force Bob to have missing homework
    students["student_02"]["homework"]["missing_tasks"] = ["Homework 1"]
    
    # Force Charlie to have both
    students["student_03"]["attendance"]["absent_yesterday"] = True
    students["student_03"]["homework"]["missing_tasks"] = ["Assignment 1"]

    db = {
        "metadata": {
            "generated_on": today.strftime("%Y-%m-%d %H:%M:%S")
        },
        "courses": courses,
        "students": students
    }

    with open("mock_db.json", "w") as f:
        json.dump(db, f, indent=4)
        
    print(f"Generated mock_db.json with {len(students)} students and {len(courses)} courses.")

if __name__ == "__main__":
    generate_db()

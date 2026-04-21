# Architecture — Student Outreach Agent

## Overview
A modular, production-ready Telegram bot that proactively messages students based on scheduled checks against a relational CSV data layer. Powered by OpenAI for context-aware, conversational outreach.

## Module Map

```
main.py              ← Entry point. Wires everything together.
├── data_manager.py  ← CSV read/query/update layer.
├── agent.py         ← LLM orchestration (OpenAI chat completions).
├── scheduler.py     ← 4 periodic task functions.
├── bot.py           ← Telegram command & message handlers.
└── setup_data.py    ← One-time script to generate sample CSV data.
```

## Data Layer (`data/`)
All state is stored in flat CSV files for transparency and portability:

| File | Purpose |
|---|---|
| `students.csv` | Student profiles, course enrollment, chat registration |
| `courses.csv` | Course ID → course name mapping |
| `sessions.csv` | Session schedule per course (date, topic) |
| `assignments.csv` | Assignment definitions per course (name, deadline) |
| `attendance.csv` | Per-student, per-session attendance status |
| `student_assignments.csv` | Per-student, per-assignment completion status |
| `interaction_logs.csv` | Timestamped log of all bot-student conversations |

## Scheduled Tasks

| # | Frequency | Trigger | Logic |
|---|---|---|---|
| 1 | Daily | `task_attendance` | Query `attendance.csv` for yesterday's absences → message absent students |
| 2 | Daily | `task_homework` | Query `student_assignments.csv` for overdue `Incomplete` entries → follow up |
| 3 | Daily | `task_reminders` | Query `sessions.csv` and `assignments.csv` for tomorrow's events → remind |
| 4 | Weekly | `task_weekly_feedback` | Message all registered students for course satisfaction and prep updates |

## LLM Integration
- **Model**: `gpt-4o-mini` via OpenAI SDK.
- **System Prompt**: Dynamically built per-student by `data_manager.build_student_context()`. Includes name, course, attendance summary, assignment status, and teacher notes.
- **Conversation Lifecycle**: The LLM appends `[RESOLVED]` or `[ESCALATED]` to its final message. The agent detects this, generates a one-sentence summary, logs it to `interaction_logs.csv`, and closes the session.

## Telegram Commands
| Command | Action |
|---|---|
| `/start` | Show welcome message and student directory |
| `/register <id>` | Link this Telegram chat to a student profile |
| `/trigger` | Run all 4 scheduled tasks immediately |
| `/status` | Show the linked student's full context |

"""
agent.py
LLM orchestration module. Handles system prompt construction,
multi-turn chat state, and interaction lifecycle (resolve / escalate).
"""

import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


class StudentAgent:
    """Manages LLM-powered conversations with students."""

    def __init__(self, data_manager):
        self.dm = data_manager
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY is not set. LLM calls will return placeholder responses.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.chats: dict[str, dict] = {}

    # ── Conversation lifecycle ───────────────────────────────

    def start_conversation(self, student_id: str, scenario: str) -> str:
        """Begin a new outreach conversation for a student."""
        context = self.dm.build_student_context(student_id)
        if not context:
            return f"Student {student_id} not found in the database."

        system_prompt = (
            "You are a professional and empathetic teaching assistant "
            "reaching out to a student on Telegram.\n\n"
            f"Scenario: {scenario}\n\n"
            f"Student Context:\n{context}\n\n"
            "Rules:\n"
            "1. Keep messages concise, warm, and grounded ONLY in the context above.\n"
            "2. Do not fabricate any facts not present in the context.\n"
            "3. When the conversation reaches a natural conclusion, append [RESOLVED] "
            "at the very end of your message.\n"
            "4. If the student expresses distress, frustration, or requests to stop, "
            "append [ESCALATED] at the very end and recommend instructor follow-up."
        )

        self.chats[student_id] = {
            "scenario": scenario,
            "history": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Compose the initial outreach message for: {scenario}"},
            ],
        }
        return self._call_llm(student_id)

    def handle_reply(self, student_id: str, user_message: str) -> str:
        """Process a student's reply and generate the next agent message."""
        if student_id not in self.chats:
            return "No active conversation found. Please wait for an outreach message."

        self.chats[student_id]["history"].append({"role": "user", "content": user_message})
        return self._call_llm(student_id)

    def is_active(self, student_id: str) -> bool:
        return student_id in self.chats

    # ── Internal helpers ─────────────────────────────────────

    def _call_llm(self, student_id: str) -> str:
        """Send the conversation history to OpenAI and return the reply."""
        session = self.chats[student_id]
        if not self.client:
            fallback = f"[LLM unavailable] Outreach for {session['scenario']}. Please set OPENAI_API_KEY."
            session["history"].append({"role": "assistant", "content": fallback})
            return fallback
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=session["history"],
            )
            reply = response.choices[0].message.content or ""
            session["history"].append({"role": "assistant", "content": reply})

            # Check for terminal flags
            if "[RESOLVED]" in reply or "[ESCALATED]" in reply:
                status = "ESCALATED" if "[ESCALATED]" in reply else "RESOLVED"
                self._close_conversation(student_id, status)

            return reply.replace("[RESOLVED]", "").replace("[ESCALATED]", "").strip()

        except Exception as e:
            logger.error("LLM call failed for %s: %s", student_id, e)
            return f"I'm having trouble connecting right now. A human instructor will follow up shortly."

    def _close_conversation(self, student_id: str, status: str):
        """Generate a summary, log to CSV, and clean up state."""
        session = self.chats[student_id]
        scenario = session["scenario"]

        # Build a compact transcript for summarization
        transcript = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in session["history"]
            if msg["role"] != "system"
        )

        try:
            summary_resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": f"Summarize this teaching assistant interaction in one sentence:\n\n{transcript}",
                }],
            )
            summary = summary_resp.choices[0].message.content or "Summary unavailable."
        except Exception:
            summary = "Summary generation failed."

        self.dm.log_interaction(student_id, scenario, status, summary.strip())
        del self.chats[student_id]
        logger.info("Conversation closed for %s — %s", student_id, status)

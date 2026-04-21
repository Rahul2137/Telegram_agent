import time
import os
from agent import StudentAgent

# Ensure the required environment variable is set
if "OPENAI_API_KEY" not in os.environ:
    print("WARNING: OPENAI_API_KEY is not set. The demo will likely fail if it attempts to call the LLM.")
    print("Please run: $env:OPENAI_API_KEY='your_key' before running this script.")

def run_demo():
    print("Initializing Student Agent...")
    agent = StudentAgent()
    
    scenarios = [
        {
            "id": "alice_01",
            "scenario": "Follow up on missing Homework 4",
            "replies": [
                "Oh no, I'm so sorry! I got overwhelmed with work.",
                "Yes, I can submit it by tomorrow evening."
            ]
        },
        {
            "id": "charlie_03",
            "scenario": "Follow up on poor attendance and see if they need help",
            "replies": [
                "I hate this course, it's way too fast and I don't understand anything. Stop bothering me."
            ]
        },
        {
            "id": "bob_02",
            "scenario": "Conduct a quick mid-course satisfaction survey",
            "replies": [
                "It's going well! I really like the material.",
                "Nope, no suggestions. Everything is perfect."
            ]
        },
        {
            "id": "diana_04",
            "scenario": "Remind about the Kaggle competition deadline this Sunday and optional Q&A tomorrow",
            "replies": [
                "Thanks! I'll definitely be at the Q&A.",
                "See you tomorrow."
            ]
        }
    ]
    
    print("\n" + "="*50)
    print("STARTING DEMO SCENARIOS")
    print("="*50 + "\n")
    
    for s in scenarios:
        student_id = s["id"]
        scenario_desc = s["scenario"]
        
        print(f"\n>>> SCENARIO: {scenario_desc} (Student: {student_id})")
        print("-" * 50)
        
        # Start interaction
        reply = agent.start_interaction(student_id, scenario_desc)
        print(f"[AGENT]: {reply}")
        time.sleep(1)
        
        # Simulate user replies
        for user_reply in s["replies"]:
            print(f"[STUDENT]: {user_reply}")
            
            # Agent responds
            reply = agent.handle_reply(student_id, user_reply)
            print(f"[AGENT]: {reply}")
            time.sleep(1)
            
            # Stop if agent closed the chat
            if student_id not in agent.chats:
                print(f"[{agent.sheet_path} updated with the interaction summary.]")
                break
                
        print("="*50)

if __name__ == "__main__":
    run_demo()

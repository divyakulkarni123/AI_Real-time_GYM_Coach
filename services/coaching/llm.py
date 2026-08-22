import os
from groq import Groq


class LLMCoach:
    def __init__(self):
        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )

    def give_feedback(self, event, issue=None):

        if event == "workout_started":
            prompt = (
                "You are a friendly AI gym coach. "
                "Give one very short motivational sentence "
                "to start the workout."
            )

        elif event == "set_completed":
            prompt = (
                "You are an AI gym coach. "
                "Give one short encouraging sentence because "
                "the user completed a set."
            )

        elif event == "workout_completed":
            prompt = (
                "You are an AI gym coach. "
                "Congratulate the user in one short sentence "
                "for completing the workout."
            )

        elif issue:
            prompt = (
                "You are an AI real-time gym coach. "
                "Give a very short spoken correction for this problem: "
                f"{issue} "
                "Maximum 15 words."
            )

        else:
            return None

        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise real-time AI gym coach. "
                        "Keep responses short, clear, and natural."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=50
        )

        return response.choices[0].message.content.strip()

import os
from groq import Groq


class LLMCoach:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY is missing.")

        self.client = Groq(api_key=api_key)

    def give_feedback(self, event, issue=None):

        # Simple fallback messages
        if event == "workout_started":
            return "Workout started. Let's begin."

        if event == "set_completed":
            return "Great job. Set completed."

        if event == "workout_completed":
            return "Excellent work. Workout completed."

        if issue:
            prompt = f"""
You are an AI gym coach.

Give short, clear voice feedback to the user.

Problem detected:
{issue}

Respond with only one short coaching sentence.
"""

        else:
            return None

        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful AI gym coach. "
                            "Give short and practical exercise feedback."
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

        except Exception as e:
            print(f"Groq error: {e}")

            # IMPORTANT: app should not crash
            if issue:
                return "Please correct your form and continue carefully."

            return None

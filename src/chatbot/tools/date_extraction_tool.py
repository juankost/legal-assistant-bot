from datetime import datetime
import re
import google.genai as genai
from dotenv import load_dotenv
from smolagents import Tool

load_dotenv()


class DateExtractionTool(Tool):
    name = "extract_temporal_context"
    description = """
    Extract temporal context from user queries using Gemini Flash.
    Identifies dates, time periods, or temporal references in questions.
    """
    inputs = {
        "query": {
            "type": "string",
            "description": "The user's question that may contain temporal references",
        }
    }
    output_type = "string"

    def __init__(self):
        super().__init__()
        self.client = genai.Client()  # Initialize the client
        self.model_name = "gemini-2.5-flash-preview-05-20"  # Store model name

    def forward(self, query: str) -> str:  # noqa
        current_date_str = datetime.now().strftime("%Y/%m/%d")
        prompt = f"""
        You are provided a chat conversation between a user and an agent about a SAG-AFTRA agreement.
        Today's date is {current_date_str}.

        Analyze the following user query and determine the temporal context of the query.
        Is the user asking about terms valid at a specific time, or a general question implying current provisions?
        
        User query: "{query}"
        
        Please identify:
        1. Specific dates mentioned (convert to YYYY/MM/DD format).
        2. Relative time references (e.g., "last year", "current", "in 2018").

        If a specific date is mentioned or can be inferred (e.g., "last year" relative to {current_date_str}), return it in YYYY/MM/DD format.
        If "current" or similar present-day references are identified, return today's date: {current_date_str}.
        If multiple dates are mentioned, return the date most directly relevant to the user's primary question. If unsure, return the most recent explicit date.
        If no specific temporal context can be confidently extracted, return a single whitespace character " ".
        
        Return ONLY the date in YYYY/MM/DD format or the single whitespace character " ". No other explanatory text.
        """  # noqa

        try:
            response = self.client.models.generate_content(model=self.model_name, contents=prompt)
            result = response.text.strip()

            if not result:  # If Gemini returns an empty string
                return None

            if not re.search(r"\d{4}/\d{2}/\d{2}", result):
                print(
                    "⚠️ Warning: Incorrect date format extracted from the query. "
                    f"Extracted date: {result}. Defaulting to current date instead!"
                )
                return None  # None will be treated as current date by the TemporalRetrievalTool

            return result

        except Exception as e:
            print(f"🚨 Error in date extraction: {e}. " f"Defaulting to None for error indication.")
            return None


if __name__ == "__main__":
    tool = DateExtractionTool()
    # Test cases
    queries = [
        "What were the rates in 2020?",
        "Tell me about the current agreement.",
        "What was the provision last year?",
        "Is there any mention of AI?",  # No date
        "Terms for 2019 vs 2021",
    ]
    for q in queries:
        print(f"Query: {q}")
        extracted_date = tool.forward(q)
        print(f"Extracted Date: '{extracted_date}'\n")

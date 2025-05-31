import os
from typing import Dict, Any, Optional, List
import logging

import google.genai as genai
from dotenv import load_dotenv
from smolagents import CodeAgent, ToolCallingAgent
from smolagents import LiteLLMModel

import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chatbot.tools.temporal_retrieval_tool import TemporalRetrievalTool
from chatbot.tools.date_extraction_tool import DateExtractionTool

load_dotenv()

print(os.getenv("GEMINI_API_KEY"))


class GeminiModel:
    """Custom wrapper for Google Gemini models to work with smolagents"""

    def __init__(self, model_name: str = "gemini-2.5-pro-preview-05-06") -> None:
        """Initialize the GeminiModel with the specified model name."""
        self.model_name = model_name
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def generate(
        self,
        messages: List[Dict[str, Any]],
        stop_sequences: Optional[List[str]] = None,
        max_tokens: int = 8192,
        temperature: float = 0.8,
    ) -> str:
        """
        Convert smolagents format to Gemini format and call the model
        """
        conversation = []
        for message in messages:
            if isinstance(message, dict):
                role = message.get("role", "user")
                content = message.get("content", "")
                if role == "system":
                    if conversation and conversation[0]["role"] == "user":
                        conversation[0]["parts"][0]["text"] = (
                            content + "\n\n" + conversation[0]["parts"][0]["text"]
                        )
                    else:
                        conversation.append({"role": "user", "parts": [{"text": content}]})
                elif role == "assistant":
                    conversation.append({"role": "model", "parts": [{"text": content}]})
                else:  # user
                    conversation.append({"role": "user", "parts": [{"text": content}]})
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=conversation,
                config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                    "stop_sequences": stop_sequences or [],
                },
            )

            return response.text
        except Exception as e:
            logging.error(f"Error calling Gemini model: {e}")
            raise


class SAGAFTRAAgent:
    def __init__(
        self,
        qdrant_path: str,
    ) -> None:
        """Initialize the SAGAFTRAAgent with the given Qdrant path."""
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY not found for SAGAFTRAAgent.")
        # self.model = LiteLLMModel(
        #     model_id="gemini-2.5-pro-preview-05-06", api_key=os.getenv("GEMINI_API_KEY")
        # )
        self.model = LiteLLMModel(api_key=os.getenv("CLAUDE_API_KEY"))
        self.retrieval_tool = TemporalRetrievalTool(qdrant_path=qdrant_path)
        self.date_tool = DateExtractionTool()

        self.system_prompt = (
            "You have been given access to the SAG-AFTRA agreements database and your task is to answer user questions about the agreements.\n"
            "When answering questions:\n"
            "1. First, identify if the question refers to a specific time period or is a general question about the agreement.\n"
            "Use the extract_temporal_context tool to determine this.\n"
            "2. Use the search_agreements tool to find agreement sections relevant to the question. "
            "The tool will return a set of agreement excerpts based on your query.\n"
            "3. Analyse the excerpts to determine if they are useful to answer the question and attempt to answer the question based on the information provided.\n"
            "4. If you require further information from the SAG-AFTRA agreements, you can call the search_agreements tool again with follow on queries.\n"
            "5. Synthesize your answer based *only* on the information provided by the initial user question and the information provided by the tools.\n"
            "6. Always cite the specific agreement, and text excerpts to support your answer.\n"
            "7. If no relevant information is found by the tools, clearly state that.\n"
            "Do not use any external knowledge or make assumptions beyond what the tools provide.\n"
        )

        self.agent = ToolCallingAgent(
            tools=[self.retrieval_tool, self.date_tool],
            model=self.model,
            # system_prompt=self.system_prompt,  # apparently this is not available in the latest version of smolagents  # noqa
            max_steps=10,
            verbosity_level=2,
            planning_interval=2,
        )

    def answer(self, question: str) -> Dict[str, Any]:
        """Process a question and return answer and sources."""

        # Add the system prompt to the agent that specifies what it will be doing specifically
        complete_query = f"""
        {self.system_prompt}
        {question}
        """
        try:
            answer_text = self.agent.run(complete_query)
            sources = self.retrieval_tool.last_structured_results
            return {"answer_text": answer_text, "sources": sources if sources else []}
        except Exception as e:
            logging.error(f"Error in SAGAFTRAAgent.answer: {e}")
            return {
                "answer_text": "An error occurred while processing your request.",
                "sources": [],
                "error": str(e),
            }


if __name__ == "__main__":
    agent = SAGAFTRAAgent(qdrant_path="data/qdrant_db")
    print(agent.answer("What is the going rate for actors in commercials?"))

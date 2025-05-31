import sys
import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from smolagents import Tool
import json
import time


ROOT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.append(os.path.join(ROOT_DIR, "src"))
from knowledge_graph.qdrant_db import QdrantDB, QueryModel, QueryConfig


class TemporalRetrievalTool(Tool):
    name = "search_agreements"
    description = """
    Search SAG-AFTRA agreements with temporal filtering. This tool retrieves agreement sections relevant to a query,
    considering the temporal context (when the agreement was valid). 
    Returns a list of relevant document chunks with their metadata.
    """  # noqa
    inputs = {
        "query": {"type": "string", "description": "The search query about SAG-AFTRA agreements"},
        "date": {
            "type": "string",
            "description": "Optional date in YYYY/MM/DD format. "
            "If provided, only retrieves agreements valid on this date",
            "nullable": True,
        },
        "top_k": {
            "type": "integer",
            "description": "Number of results to retrieve (default: 5)",
            "nullable": True,
        },
    }
    output_type = "string"
    last_structured_results: List[Dict[str, Any]] = []

    def __init__(self, qdrant_path: str, collection_name: str = "sftra_agreements"):
        super().__init__()
        self.db = QdrantDB(collection_name=collection_name, qdrant_path=qdrant_path)
        self.last_structured_results = []

    def forward(self, query: str, date: Optional[str] = None, top_k: int = 5) -> str:
        self.last_structured_results = []
        if date:
            if not re.search(r"\d{4}/\d{2}/\d{2}", date):
                return f"Invalid date format: {date}. Please use YYYY/MM/DD format."

        query_model = QueryModel(query=query, date=date)
        config = QueryConfig(top_k=top_k)
        results = self.db.retrieve(query_model, config)

        if not results:
            self.last_structured_results = []
            return "No relevant documents found."

        structured_docs_for_agent = [result.payload for result in results]
        formatted_results_for_llm = []

        for i, result in enumerate(results):
            payload = result.payload

            formatted_results_for_llm.append(
                f"**Result {i+1}**\n"
                f"Agreement: {payload['agreement_title']}\n"
                f"Agreement URL: {payload['agreement_url']}\n"
                f"Valid from: {payload.get('valid_from', 'Undefined')}\n"
                f"Valid to: {payload.get('valid_to', 'Undefined')}\n"
                f"Category: {payload.get('category', 'Undefined')}\n"
                f"Subcategory: {payload.get('subcategory', 'Undefined')}\n"
                f"Text excerpt: {payload['chunk_text']}\n"
                f"Previous context: {payload['previous_context']}\n"
                f"Following context: {payload['following_context']}\n"
                f"Impacted agreements: {json.dumps(payload['impacted_agreements'], indent=2)}\n"
            )

        self.last_structured_results = structured_docs_for_agent
        return "\n---\n".join(formatted_results_for_llm)  # Return string summary for LLM


if __name__ == "__main__":

    COLLECTION_NAME = "sftra_agreements"
    QDRANT_PATH = os.path.join(ROOT_DIR, "data", "qdrant_db")
    tool = TemporalRetrievalTool(qdrant_path=QDRANT_PATH, collection_name=COLLECTION_NAME)
    print(tool.forward("What is the validity of the agreement for the Commercials?"))

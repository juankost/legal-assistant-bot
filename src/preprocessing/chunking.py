# This script chunks the markdown and then creates JSONs for each chunk with the additional
# metadata that I want to store.

import os
import json
import hashlib
import pandas as pd
from tqdm import tqdm
from typing import List, Dict, Any
from thefuzz import process
import ast

ROOT_DIR = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot"
METADATA_PATH = os.path.join(ROOT_DIR, "data", "agreement_metadata.csv")
CHUNKS_DIR = os.path.join(ROOT_DIR, "data", "chunks")
ANNOTATION_FILE_PATH = os.path.join(ROOT_DIR, "data", "agreement_validity.csv")


def length_based_chunking(text: str, config: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Chunk the text based on token length.

    Args:
        text: The text to chunk
        config: Configuration dictionary containing chunking parameters:
            - chunk_size: Approximate number of tokens in a chunk
            - chunk_overlap: Number of tokens to overlap between chunks
            - chars_per_token: Characters per token approximation (default 3.6)

    Returns:
        List of dictionaries with chunk_text, previous_context, and following_context
    """
    chunk_size = config.get("chunk_size", 1000)
    chunk_overlap = config.get("chunk_overlap", 100)
    chars_per_token = config.get("chars_per_token", 3.6)

    char_size = int(chunk_size * chars_per_token)
    overlap_char_size = int(chunk_overlap * chars_per_token)

    if len(text) <= char_size:
        return [{"chunk_text": text, "previous_context": "", "following_context": ""}]

    chunks = []
    chunk_positions = []
    start = 0
    end = char_size

    # First pass: determine chunk boundaries
    while start < len(text):
        if end >= len(text):
            chunk_positions.append((start, len(text)))
            break

        # Try to find a good breaking point (newline or space)
        break_point = text.rfind("\n\n", start, end)
        if break_point == -1 or break_point <= start:
            break_point = text.rfind("\n", start, end)
            if break_point == -1 or break_point <= start:
                break_point = text.rfind(" ", start, end)
                if break_point == -1 or break_point <= start:
                    break_point = end

        chunk_positions.append((start, break_point))
        start = break_point
        end = start + char_size

    # Second pass: create chunks with context
    for i, (chunk_start, chunk_end) in enumerate(chunk_positions):
        chunk_text = text[chunk_start:chunk_end]

        # Calculate previous context
        prev_context_start = max(0, chunk_start - overlap_char_size)
        previous_context = (
            text[prev_context_start:chunk_start] if prev_context_start < chunk_start else ""
        )

        # Calculate following context
        next_context_end = min(len(text), chunk_end + overlap_char_size)
        following_context = text[chunk_end:next_context_end] if chunk_end < next_context_end else ""

        chunks.append(
            {
                "chunk_text": chunk_text,
                "previous_context": previous_context,
                "following_context": following_context,
            }
        )

    return chunks


def chunk_markdown(markdown_path, chunking_config):
    """
    Chunk a markdown file and return the chunks.

    Args:
        markdown_path: Path to the markdown file
        chunking_config: Configuration for chunking

    Returns:
        List of chunk dictionaries
    """
    with open(markdown_path, "r") as f:
        markdown_text = f.read()

    # Chunk the markdown text
    chunks = length_based_chunking(markdown_text, chunking_config)

    return chunks


def create_chunk_hash(chunk_text):
    """
    Create a hash for a chunk.

    Args:
        chunk_text: Text of the chunk

    Returns:
        Hash string for the chunk
    """
    return hashlib.md5(chunk_text.encode("utf-8")).hexdigest()


def get_summaries_of_impacted_agreements(impacted_agreements_list, agreement_title_summary_dict):

    enriched_impacted_agreements_list = []

    # Handle various formats of impacted_agreements_list
    if pd.isna(impacted_agreements_list):
        actual_agreements_list = []
    elif isinstance(impacted_agreements_list, str):
        if impacted_agreements_list.startswith("[") and impacted_agreements_list.endswith("]"):
            try:
                actual_agreements_list = ast.literal_eval(impacted_agreements_list)
            except (ValueError, SyntaxError):
                actual_agreements_list = [
                    s.strip() for s in impacted_agreements_list.strip("[]").split(",") if s.strip()
                ]  # Fallback for malformed lists
        else:
            actual_agreements_list = [
                s.strip() for s in impacted_agreements_list.split(",") if s.strip()
            ]
    elif isinstance(impacted_agreements_list, list):
        actual_agreements_list = impacted_agreements_list
    else:
        actual_agreements_list = []

    available_titles = list(agreement_title_summary_dict.keys())

    for agreement_title in actual_agreements_list:
        summary = None
        if agreement_title in agreement_title_summary_dict:
            summary = agreement_title_summary_dict[agreement_title]
        elif available_titles:  # Only attempt fuzzy match if there are titles to match against
            # Fuzzy match
            best_match = process.extractOne(agreement_title, available_titles)
            if best_match and best_match[1] >= 80:
                summary = agreement_title_summary_dict[best_match[0]]

        if summary:
            enriched_impacted_agreements_list.append(
                {
                    "impacted_agreement_title": agreement_title,
                    "impacted_agreement_summary": summary,
                }
            )
    return enriched_impacted_agreements_list


def process_markdown_files():
    """
    Process all markdown files according to the implementation plan.
    """
    os.makedirs(CHUNKS_DIR, exist_ok=True)
    metadata_df = pd.read_csv(METADATA_PATH)

    # Add the validity information and impacted agreements to the metadata
    annotation_df = pd.read_csv(ANNOTATION_FILE_PATH)
    annotation_df = annotation_df[
        ["agreement_id", "mturk_valid_from", "mturk_valid_to", "mturk_impacted_agreements"]
    ]
    metadata_df = pd.merge(metadata_df, annotation_df, on="agreement_id", how="left")

    # Create a direct mapping from agreement_title to summary
    agreement_title_summary_dict = pd.Series(
        metadata_df.summary.values, index=metadata_df.agreement_title
    ).to_dict()

    chunking_config = {
        "chunk_size": 300,  # tokens
        "chunk_overlap": 100,  # tokens
        "chars_per_token": 3.6,  # approximation for average characters per token
    }

    # Convert NaN strings to None
    metadata_df = metadata_df.fillna(value="")

    for _, row in tqdm(
        metadata_df.iterrows(), total=len(metadata_df), desc="Processing markdown files"
    ):
        markdown_path = row["markdown_path"]
        agreement_id = row["agreement_id"]
        if pd.isna(markdown_path) or not os.path.exists(markdown_path):
            continue

        chunks = chunk_markdown(markdown_path, chunking_config)
        for i, chunk_dict in enumerate(chunks):
            chunk_text = chunk_dict["chunk_text"]
            chunk_hash = create_chunk_hash(chunk_text)

            # Ensure mturk_impacted_agreements is passed correctly
            impacted_agreements_input = row["mturk_impacted_agreements"]
            enriched_impacted_agreements_list = get_summaries_of_impacted_agreements(
                impacted_agreements_input, agreement_title_summary_dict
            )
            chunk_data = {
                "agreement_id": agreement_id,
                "agreement_title": row["agreement_title"],
                "agreement_url": row["agreement_url"],
                "agreement_info": row["agreement_info"],
                "category": row["category"],
                "subcategory": (
                    row["subcategory"] if not pd.isna(row["subcategory"]) else "No subcategory"
                ),
                "chunk_index": i,
                "chunk_text": chunk_text,
                "previous_context": chunk_dict["previous_context"],
                "following_context": chunk_dict["following_context"],
                "valid_from": row["mturk_valid_from"],
                "valid_to": row["mturk_valid_to"],
                "impacted_agreements": enriched_impacted_agreements_list,
                "chunk_hash": chunk_hash,
                "total_chunks": len(chunks),
            }

            chunk_filename = f"agreement_{agreement_id}_chunk_{i}.json"
            chunk_path = os.path.join(CHUNKS_DIR, chunk_filename)
            with open(chunk_path, "w") as f:
                json.dump(chunk_data, f, indent=2)

    print(f"Processing complete. Chunks saved to {CHUNKS_DIR}")


if __name__ == "__main__":
    process_markdown_files()

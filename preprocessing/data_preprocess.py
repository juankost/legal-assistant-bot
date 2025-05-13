import pandas as pd
import os
import sys
import logging
from mistralai import Mistral

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import retry_on_error  # noqa: E402
from scraper.llm_scraper import call_gemini  # noqa: E402
from preprocessing.prompts import AGREEMENT_VALIDITY_PROMPT  # noqa: E402

DATA_DIR = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data"


@retry_on_error()
def convert_pdf_to_markdown(pdf_path, markdown_path):

    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    uploaded_pdf = client.files.upload(
        file={
            "file_name": pdf_path,
            "content": open(pdf_path, "rb"),
        },
        purpose="ocr",
    )

    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": client.files.get_signed_url(file_id=uploaded_pdf.id).url,
        },
    )

    markdown_text = ""
    for page in ocr_response.pages:
        markdown_text += page.markdown

    with open(markdown_path, "w") as f:
        f.write(markdown_text)

    return


def process_agreement_pdfs(agreements_path, output_dir):
    data = pd.read_csv(agreements_path)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    markdown_paths = []
    for idx, row in data.iterrows():
        if "raw_path" not in row or not row["raw_path"] or pd.isna(row["raw_path"]):
            print(f"Skipping row {idx}: No valid raw_path found")
            markdown_paths.append(None)
            continue

        pdf_path = row["raw_path"]
        if not os.path.exists(pdf_path):
            print(f"Skipping {pdf_path}: File not found")
            markdown_paths.append(None)
            continue

        print(f"Processing PDF {idx+1}/{len(data)}: {pdf_path}")
        file_name = os.path.basename(p=pdf_path).split(".pdf")[0] + ".md"
        markdown_path = os.path.join(output_dir, file_name)
        logging.info(f"Converting {pdf_path} to {markdown_path}")

        convert_pdf_to_markdown(pdf_path, markdown_path)
        markdown_paths.append(markdown_path)

    data["markdown_path"] = markdown_paths
    data.to_csv(agreements_path, index=False)
    print(f"Updated {agreements_path} with markdown file paths")


def add_agreement_id_to_metadata(agreements_csv_path):
    """
    Adds a unique agreement_id column to the agreement metadata CSV if it doesn't exist.

    Args:
        agreements_csv_path: Path to the agreement metadata CSV file
    """
    data = pd.read_csv(agreements_csv_path)

    if "agreement_id" not in data.columns:
        print("Adding agreement_id column to metadata")
        data["agreement_id"] = range(len(data))
        data.to_csv(agreements_csv_path, index=False)
        print(f"Updated {agreements_csv_path} with agreement_id column")
    else:
        print("agreement_id column already exists in metadata")

    return data


def get_agreements_validity_period(agreements_csv_path, overwrite=False):
    """
    Analyze agreement documents to determine validity periods and relationships.

    Args:
        agreements_csv_path: Path to CSV file containing agreement metadata
        overwrite: If True, re-process agreements even if they were already analyzed

    Returns:
        DataFrame containing the analysis results
    """
    # First ensure we have agreement_ids in the metadata
    data = add_agreement_id_to_metadata(agreements_csv_path)

    # Define output path for results
    output_path = os.path.join(
        os.path.dirname(agreements_csv_path), "agreement_validity_analysis.csv"
    )

    # Load existing results if file exists
    if os.path.exists(output_path):
        results_df = pd.read_csv(output_path)
        processed_ids = set(results_df["agreement_id"])
        print(f"Found existing analysis file with {len(processed_ids)} agreements")
    else:
        results_df = pd.DataFrame(
            columns=[
                "agreement_id",
                "agreement_title",
                "validity_from",
                "valid_to",
                "impacted_agreements",
            ]
        )
        processed_ids = set()
        print("Starting new analysis file")

    for _, row in data.iterrows():
        agreement_id = row["agreement_id"]

        # Skip if already processed and overwrite is False
        if agreement_id in processed_ids and not overwrite:
            print(
                f"Skipping agreement {agreement_id}: Already processed (use overwrite=True to re-process)"
            )
            continue

        if "markdown_path" not in row or not row["markdown_path"] or pd.isna(row["markdown_path"]):
            print(f"Skipping agreement {agreement_id}: No valid markdown_path found")
            continue

        markdown_path = row["markdown_path"]
        if not os.path.exists(markdown_path):
            print(f"Skipping {markdown_path}: File not found")
            continue

        print(f"Processing agreement {agreement_id}: {row['agreement_title']}")

        # Read the markdown content (first 10k characters only)
        with open(markdown_path, "r") as f:
            agreement_text = f.read(10000)

        # Get all agreement titles for reference
        all_agreements_titles = data["agreement_title"].dropna().tolist()

        # Create prompt for LLM
        formatted_titles = "\n".join([f"- {title}" for title in all_agreements_titles])
        prompt = AGREEMENT_VALIDITY_PROMPT.format(
            title=row["agreement_title"],
            info=row.get("agreement_info", ""),
            text=agreement_text,
            all_titles=formatted_titles,
        )

        # Call Gemini to analyze the agreement
        response_schema = {
            "type": "object",
            "properties": {
                "validity_from": {"type": "string"},
                "valid_to": {"type": "string"},
                "impacted_agreements": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["validity_from", "valid_to", "impacted_agreements"],
        }

        analysis = call_gemini(
            prompt=prompt,
            model_name="gemini-2.5-pro-preview-03-25",
            response_schema=response_schema,
        )

        if analysis:
            # Add analysis to results
            result = {
                "agreement_id": agreement_id,
                "agreement_title": row["agreement_title"],
                "validity_from": analysis.get("validity_from", ""),
                "valid_to": analysis.get("valid_to", ""),
                "impacted_agreements": analysis.get("impacted_agreements", []),
            }

            # Remove existing entry if overwrite is True
            if agreement_id in processed_ids and overwrite:
                results_df = results_df[results_df["agreement_id"] != agreement_id]

            # Add new result to DataFrame
            new_row = pd.DataFrame([result])
            results_df = pd.concat([results_df, new_row], ignore_index=True)

            # Save results after each agreement
            results_df.to_csv(output_path, index=False)
            processed_ids.add(agreement_id)

            print(
                f"  Analysis complete: Valid from {result['validity_from']} to {result['valid_to']}"
            )
            if result["impacted_agreements"]:
                impacted = ", ".join(result["impacted_agreements"][:2])
                if len(result["impacted_agreements"]) > 2:
                    impacted += f" and {len(result['impacted_agreements'])-2} more"
                print(f"  Impacts {len(result['impacted_agreements'])} agreements: {impacted}")
        else:
            print(f"  Failed to analyze agreement {row['agreement_title']}")

    print(f"Analysis complete. Results saved to {output_path}")
    return results_df


if __name__ == "__main__":
    agreements_path = os.path.join(DATA_DIR, "raw", "agreement_metadata.csv")
    output_dir = os.path.join(DATA_DIR, "markdown")

    # Add agreement_id to the metadata if needed
    add_agreement_id_to_metadata(agreements_path)

    # Process agreements
    # process_agreement_pdfs(agreements_path, output_dir)
    get_agreements_validity_period(agreements_path, overwrite=False)

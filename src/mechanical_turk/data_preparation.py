import csv
import json
import os
import pandas as pd

# Assumptions:
# METADATA_PATH: Path to a CSV file containing agreement metadata.
# Example: 'data/processed/agreement_metadata.csv' (derived from README structure)
# Columns expected: 'agreement_id', 'agreement_title', 'markdown_path', 'agreement_info', 'agreement_url' (though PRD says 'agreement_url' is in METADATA_PATH but also to be generated)

# VALIDITY_ANALYSIS_PATH: Path to a CSV file containing LLM extracted data.
# Example: 'data/processed/validity_analysis.csv'
# Columns expected: 'agreement_id', 'validity_from', 'valid_to', 'impacted_agreements'
# Crucially, this script assumes that LLM justifications are either in this file or can be easily joined.
# For simplicity, let's assume 'llm_validity_from_justification', 'llm_valid_to_justification',
# 'llm_impacted_agreements_justifications' (a JSON string or similar structure) are available,
# possibly by augmenting the process that creates VALIDITY_ANALYSIS_PATH as per PRD.

# ALL_AGREEMENT_TITLES: A list of all possible agreement titles.
# Example: Will be loaded from a file or passed as an argument. Let's assume a JSON file for now.
# Example path: 'data/processed/all_agreement_titles.json'

# CLOUD_STORAGE_BASE_URL: Base URL for the cloud storage where markdown files will be hosted.
# Example: "https://your-cloud-storage-provider.com/bucket-name/" (User needs to configure this)

METADATA_PATH = "data/processed/agreement_metadata.csv"  # Placeholder
VALIDITY_ANALYSIS_PATH = "data/processed/validity_analysis.csv"  # Placeholder
ALL_AGREEMENT_TITLES_PATH = "data/processed/all_agreement_titles.json"  # Placeholder
MTURK_INPUT_CSV_PATH = "data/mturk/input/mturk_tasks.csv"
CLOUD_STORAGE_BASE_URL = "https://example-bucket.s3.amazonaws.com/agreements/"  # Placeholder


def upload_to_cloud_storage(markdown_file_path, agreement_id):
    """
    Placeholder function to simulate uploading a markdown file to cloud storage.
    In a real implementation, this would use a cloud provider's SDK (e.g., boto3 for AWS S3).
    Args:
        markdown_file_path (str): The local path to the markdown file.
        agreement_id (str): The agreement ID, used for naming in the cloud.
    Returns:
        str: The public URL of the uploaded file.
    """
    # Simulate upload: In reality, upload the file and get a public URL.
    # Ensure file naming in cloud storage is unique and identifiable.
    # For example, using agreement_id in the path.
    if not os.path.exists(markdown_file_path):
        print(f"Warning: Markdown file not found: {markdown_file_path}")
        return f"{CLOUD_STORAGE_BASE_URL}{agreement_id}_text.md"  # Return a hypothetical URL

    # Actual upload logic would go here.
    # e.g., s3_client.upload_file(markdown_file_path, BUCKET_NAME, f"agreements/{agreement_id}_text.md")
    print(f"Simulating upload of {markdown_file_path} for agreement {agreement_id}")
    return f"{CLOUD_STORAGE_BASE_URL}{agreement_id}_text.md"


def prepare_mturk_input_csv(
    metadata_csv_path, validity_analysis_csv_path, all_agreement_titles_json_path, output_csv_path
):
    """
    Prepares a CSV file for batch uploading to Amazon Mechanical Turk.
    Combines agreement metadata, LLM extractions, and LLM justifications.
    Uploads agreement texts to cloud storage and generates public URLs.
    """
    try:
        df_metadata = pd.read_csv(metadata_csv_path)
        df_validity = pd.read_csv(validity_analysis_csv_path)
    except FileNotFoundError as e:
        print(f"Error: Input file not found. {e}")
        print("Please ensure METADATA_PATH and VALIDITY_ANALYSIS_PATH point to valid CSV files.")
        print("You might need to create dummy CSV files with expected columns for testing:")
        print(
            f"  {metadata_csv_path}: agreement_id, agreement_title, markdown_path, agreement_info"
        )
        print(
            f"  {validity_analysis_csv_path}: agreement_id, validity_from, valid_to, impacted_agreements, llm_validity_from_justification, llm_valid_to_justification, llm_impacted_agreements_justified_json"
        )
        return

    if "agreement_id" not in df_metadata.columns or "agreement_id" not in df_validity.columns:
        print("Error: 'agreement_id' column missing from one of the input CSVs. Cannot merge.")
        return

    # Merge data
    df_merged = pd.merge(df_metadata, df_validity, on="agreement_id", how="inner")

    if df_merged.empty:
        print(
            "Warning: No data after merging metadata and validity analysis. Output CSV will be empty or not generated."
        )
        # return # Decided to proceed to create an empty CSV with headers if no data

    try:
        with open(all_agreement_titles_json_path, "r") as f:
            all_agreement_titles = json.load(f)
        all_agreement_titles_json_str = json.dumps(all_agreement_titles)
    except FileNotFoundError:
        print(
            f"Warning: {all_agreement_titles_json_path} not found. 'all_agreement_titles_json' will be empty."
        )
        all_agreement_titles_json_str = json.dumps([])
    except json.JSONDecodeError:
        print(
            f"Warning: Could not decode JSON from {all_agreement_titles_json_path}. 'all_agreement_titles_json' will be empty."
        )
        all_agreement_titles_json_str = json.dumps([])

    mturk_data = []
    task_id_counter = 1

    expected_validity_cols = [
        "validity_from",
        "llm_validity_from_justification",
        "valid_to",
        "llm_valid_to_justification",
        "impacted_agreements_justified_json",  # PRD uses llm_impacted_agreements_justified_json
        # but earlier it uses impacted_agreements.
        # Assuming this column in df_validity contains the pre-formatted JSON
        # as per SCHEMA_FIX_IMPACTED_AGREEMENTS
    ]

    for col in expected_validity_cols:
        if col not in df_merged.columns:
            print(
                f"Warning: Expected column '{col}' not found in merged data. It will be empty in the output."
            )
            df_merged[col] = pd.NA  # Add missing columns with NA

    for _, row in df_merged.iterrows():
        agreement_id = row["agreement_id"]
        markdown_path = row.get("markdown_path", "")  # Ensure markdown_path exists

        # Generate public URL for agreement text
        # PRD says markdown_path is in METADATA_PATH.
        agreement_text_url = upload_to_cloud_storage(markdown_path, agreement_id)

        # Ensure justifications are present, using pd.NA or empty string if not
        # PRD: "The system must ensure that justifications generated by the LLM ... are available"
        # This script assumes they are already in df_validity or made available.
        # Let's assume df_validity contains:
        # - llm_validity_from_justification
        # - llm_valid_to_justification
        # - llm_impacted_agreements_justified_json (already a JSON string as per PRD)

        task_data = {
            "task_id": f"task_{task_id_counter}",
            "agreement_id": agreement_id,
            "agreement_title": row.get("agreement_title", ""),
            "agreement_info": row.get("agreement_info", ""),  # As used in Notebook Cell 5
            "agreement_text_url": agreement_text_url,
            "llm_validity_from": row.get("validity_from", pd.NA),
            "llm_validity_from_justification": row.get("llm_validity_from_justification", ""),
            "llm_valid_to": row.get("valid_to", pd.NA),
            "llm_valid_to_justification": row.get("llm_valid_to_justification", ""),
            "llm_impacted_agreements_justified_json": row.get(
                "impacted_agreements_justified_json", "[]"
            ),  # PRD spec
            "all_agreement_titles_json": all_agreement_titles_json_str,
        }
        mturk_data.append(task_data)
        task_id_counter += 1

    if not mturk_data and df_merged.empty:
        print("No data to write to MTurk input CSV.")

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)

    # Define output columns based on PRD Section 4.1 "Output (MTurk Input CSV Columns)"
    output_columns = [
        "task_id",
        "agreement_id",
        "agreement_title",
        "agreement_info",
        "agreement_text_url",
        "llm_validity_from",
        "llm_validity_from_justification",
        "llm_valid_to",
        "llm_valid_to_justification",
        "llm_impacted_agreements_justified_json",
        "all_agreement_titles_json",
    ]

    try:
        with open(output_csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=output_columns)
            writer.writeheader()
            if mturk_data:
                writer.writerows(mturk_data)
        print(f"MTurk input CSV successfully created at: {output_csv_path}")
        if not mturk_data and not df_merged.empty:
            print(
                f"MTurk input CSV created with headers only, as the merged dataframe was not empty but produced no rows for mturk_data: {output_csv_path}"
            )
        elif not mturk_data:
            print(
                f"MTurk input CSV created with headers only, as there was no data after merge: {output_csv_path}"
            )

    except IOError as e:
        print(f"Error writing MTurk input CSV: {e}")


if __name__ == "__main__":
    # Create dummy input files for testing if they don't exist
    # This is helpful for initial setup and running the script directly.

    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("data/mturk/input", exist_ok=True)

    if not os.path.exists(METADATA_PATH):
        print(f"Creating dummy {METADATA_PATH}")
        dummy_metadata = pd.DataFrame(
            [
                {
                    "agreement_id": "AGR001",
                    "agreement_title": "Test Agreement 1",
                    "markdown_path": "data/markdown/AGR001.md",
                    "agreement_info": "Info for AGR001",
                },
                {
                    "agreement_id": "AGR002",
                    "agreement_title": "Test Agreement 2",
                    "markdown_path": "data/markdown/AGR002.md",
                    "agreement_info": "Info for AGR002",
                },
            ]
        )
        dummy_metadata.to_csv(METADATA_PATH, index=False)
        os.makedirs("data/markdown", exist_ok=True)
        with open("data/markdown/AGR001.md", "w") as f:
            f.write("# Test Agreement 1 Content")
        with open("data/markdown/AGR002.md", "w") as f:
            f.write("# Test Agreement 2 Content")

    if not os.path.exists(VALIDITY_ANALYSIS_PATH):
        print(f"Creating dummy {VALIDITY_ANALYSIS_PATH}")
        dummy_validity = pd.DataFrame(
            [
                {
                    "agreement_id": "AGR001",
                    "validity_from": "2023/01/01",
                    "llm_validity_from_justification": "LLM says so for VF1.",
                    "valid_to": "2023/12/31",
                    "llm_valid_to_justification": "LLM reasons for VT1.",
                    "impacted_agreements_justified_json": json.dumps(
                        [
                            {
                                "impacted_agreement_title": "SubAgrA",
                                "justification": "Linked by section 5.",
                            }
                        ]
                    ),
                },
                {
                    "agreement_id": "AGR002",
                    "validity_from": "2024/XX/XX",
                    "llm_validity_from_justification": "VF2 is uncertain.",
                    "valid_to": "Indefinite",
                    "llm_valid_to_justification": "VT2 is ongoing.",
                    "impacted_agreements_justified_json": json.dumps([]),
                },
            ]
        )
        dummy_validity.to_csv(VALIDITY_ANALYSIS_PATH, index=False)

    if not os.path.exists(ALL_AGREEMENT_TITLES_PATH):
        print(f"Creating dummy {ALL_AGREEMENT_TITLES_PATH}")
        with open(ALL_AGREEMENT_TITLES_PATH, "w") as f:
            json.dump(["Test Agreement 1", "Test Agreement 2", "SubAgrA", "Another Title"], f)

    print(
        f"Running data preparation script. Ensure input files exist or dummy files will be created:"
    )
    print(f"  Metadata: {METADATA_PATH}")
    print(f"  Validity Analysis: {VALIDITY_ANALYSIS_PATH}")
    print(f"  All Titles: {ALL_AGREEMENT_TITLES_PATH}")
    print(f"  Output MTurk CSV: {MTURK_INPUT_CSV_PATH}")

    prepare_mturk_input_csv(
        METADATA_PATH, VALIDITY_ANALYSIS_PATH, ALL_AGREEMENT_TITLES_PATH, MTURK_INPUT_CSV_PATH
    )

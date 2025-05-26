import os
import pandas as pd
import tqdm

# Actual input datasets schema:
# validity_analysis.csv: agreement_id,agreement_title,validity_from,valid_to,impacted_agreements
# impacted_agreements has the format ["Title 1", "Title 2", ...]
# validity_from and validity_to have format YYYY/MM/DD (or YYYY/MM/XX or YYYY/XX/XX)
# the rest are strings

# agreement_metadata.csv:agreement_id,agreement_title,agreement_url,agreement_info,category,subcategory,url,raw_path,markdown_path,agreement_id
# String format for all fields

ROOT_PATH = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot"
METADATA_PATH = os.path.join(ROOT_PATH, "data", "agreement_metadata.csv")
VALIDITY_ANALYSIS_PATH = os.path.join(ROOT_PATH, "data", "agreement_validity_analysis.csv")
MTURK_DATA_PATH = os.path.join(ROOT_PATH, "data", "mturk", "input")
MTURK_TASKS_CSV_PATH = os.path.join(MTURK_DATA_PATH, "mturk_tasks.csv")


def prepare_mturk_input_csv(
    metadata_csv_path,
    validity_analysis_csv_path,
    output_csv_path,
):
    """
    Prepares a CSV file for batch uploading to Amazon Mechanical Turk.
    Combines agreement metadata and LLM extractions.
    """
    df_metadata = pd.read_csv(metadata_csv_path)
    df_validity = pd.read_csv(validity_analysis_csv_path)

    if "agreement_id" not in df_metadata.columns or "agreement_id" not in df_validity.columns:
        raise ValueError("Error: 'agreement_id' missing from one of the input CSVs.")

    df_merged = pd.merge(
        df_metadata, df_validity, on=["agreement_id", "agreement_title"], how="inner"
    )

    if df_merged.empty:
        raise ValueError("Error when merging files. Output CSV will be empty or not generated.")

    mturk_data = []
    task_id_counter = 1

    expected_input_validity_cols = ["validity_from", "valid_to", "impacted_agreements"]
    assert all(
        col in df_merged.columns for col in expected_input_validity_cols
    ), "Error: Expected input columns not found in merged data."

    for _, row in tqdm.tqdm(df_merged.iterrows(), total=len(df_merged)):
        task_data = {
            # "task_id": f"task_{task_id_counter}",
            "radioName": "validation",  # Added required field
            "agreement_id": row["agreement_id"],
            "agreement_title": row.get("agreement_title", ""),
            "agreement_text_url": row["agreement_url"],
            "system_validity_from": row.get("validity_from", pd.NA),
            "system_valid_to": row.get("valid_to", pd.NA),
            "system_impacted_agreements_string": row.get("impacted_agreements", "[]")[
                1:-1
            ],  # remove []  # noqa
        }
        mturk_data.append(task_data)
        task_id_counter += 1

    output_columns = [
        # "task_id",
        "radioName",
        "agreement_id",
        "agreement_title",
        "agreement_text_url",
        "system_validity_from",
        "system_valid_to",
        "system_impacted_agreements_string",
    ]
    mturk_df = pd.DataFrame(mturk_data, columns=output_columns)
    mturk_df.to_csv(output_csv_path, index=False)


if __name__ == "__main__":

    print(
        "Running data preparation script. Ensure input files exist or dummy files will be created:"
    )
    print(f"  Metadata: {METADATA_PATH}")
    print(f"  Validity Analysis: {VALIDITY_ANALYSIS_PATH}")
    print(f"  Ou`tput MTurk CSV: {MTURK_TASKS_CSV_PATH}")

    prepare_mturk_input_csv(
        METADATA_PATH,
        VALIDITY_ANALYSIS_PATH,
        MTURK_TASKS_CSV_PATH,
    )

    MTURK_TASKS_CSV_PATH = os.path.join(MTURK_DATA_PATH, "mturk_tasks.csv")
    mturk_tasks_text_csv_path = os.path.join(MTURK_DATA_PATH, "mturk_tasks_text.csv")

    df = pd.read_csv(MTURK_TASKS_CSV_PATH).head(5)
    df.to_csv(mturk_tasks_text_csv_path, index=False)

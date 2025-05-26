import csv
import pandas as pd
import os
from collections import Counter

# Assumptions:
# ANNOTATION_FILE_PATH: Path to the main annotation CSV file that needs to be updated.
# Example: 'data/processed/annotations.csv'
# MTURK_OUTPUT_RAW_CSV_PATH: Path to the CSV file downloaded from MTurk containing worker responses.
# Example: 'data/mturk/output/mturk_results_raw.csv'
# MTURK_INPUT_PROCESSED_PATH: Path to the CSV file that was uploaded to MTurk (output of data_preparation.py).
# This is needed to fetch the original 'system_' values shown to the worker.
# Example: 'data/mturk/input/mturk_tasks.csv'

DATA_DIR = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data"
ANNOTATION_FILE_PATH = os.path.join(DATA_DIR, "agreement_validity.csv")
MTURK_OUTPUT_RAW_CSV_PATH = os.path.join(DATA_DIR, "mturk", "output", "mturk_results_raw.csv")
MTURK_INPUT_PROCESSED_PATH = os.path.join(DATA_DIR, "mturk", "input", "mturk_tasks.csv")


def validate_date_format(date_str):
    """Validates if the date string matches YYYY/MM/DD, YYYY/MM/XX, YYYY/XX/XX, or Indefinite."""
    if date_str == "Indefinite":
        return True
    if not isinstance(date_str, str):
        return False
    parts = date_str.split("/")
    if len(parts) == 3:
        year, month, day = parts
        if (
            len(year) == 4
            and year.isdigit()
            and (len(month) == 2 and (month.isdigit() or month == "XX"))
            and (len(day) == 2 and (day.isdigit() or day == "XX"))
        ):
            return True
    return False


def validate_comma_separated_quoted_strings(value_str):
    """
    Validates if the string is a comma-separated list of double-quoted strings,
    or an empty string "".
    Examples: "Title A", "Title B, with comma"
                ""
                "Single Title"
    Allows for escaped quotes inside the titles.
    """
    if not isinstance(value_str, str):
        return False
    if value_str == '""':  # Empty string for no agreements
        return True
    if not value_str:  # Truly empty string is invalid, must be ""
        return False

    # Let's use a simpler check that it's not obviously wrong, rather than a complex regex.
    # The PRD emphasizes clear instructions and examples for the worker.
    # We'll check if it's an empty string for "no agreements" or seems to be quoted.
    if value_str == '""':
        return True
    # Check if it starts and ends with a quote, and is not just a single quote or similar error
    if value_str.startswith('"') and value_str.endswith('"') and len(value_str) >= 2:
        # This is a basic check. Further parsing could be done if strict validation is critical.
        # For example, ensuring that internal quotes are properly escaped or that commas
        # only appear between correctly quoted segments.
        # Given MTurk context, this might be sufficient if combined with clear instructions.
        return True
    return False


def get_consensus_value(series):
    """Gets the majority vote for a series of values. Returns pd.NA if no clear majority."""
    if series.empty:
        return pd.NA
    # Ensure all values are hashable, e.g. convert lists/dicts in series to tuples/strings if necessary
    # For this script, expecting simple types or booleans mostly.
    try:
        counts = Counter(series.dropna())
    except TypeError:
        # Handle unhashable types if they occur, e.g. by converting to string
        counts = Counter(series.dropna().astype(str))

    if not counts:
        return pd.NA
    most_common_items = counts.most_common()
    if len(most_common_items) == 1 or (
        len(most_common_items) > 1 and most_common_items[0][1] > most_common_items[1][1]
    ):
        return most_common_items[0][0]
    return pd.NA  # Or some other indicator of disagreement / tie


def process_mturk_results(
    mturk_results_csv_path,
    annotations_csv_path,
    # Path to the data sent to MTurk, to retrieve original system values
    original_system_data_path,
):
    """
    Processes results from MTurk, performs validation, consolidation,
    and updates the main annotation file.
    """
    try:
        df_mturk_results = pd.read_csv(mturk_results_csv_path)
    except FileNotFoundError:
        print(f"Error: MTurk results file not found at {mturk_results_csv_path}.")
        print("Please ensure the path is correct or create a dummy file for testing.")
        print(
            "Expected columns (example): agreement_id, human_validity_from_is_correct, human_validity_from_corrected, human_impacted_agreements_corrected_string, ..."
        )
        return

    if df_mturk_results.empty:
        print("MTurk results CSV is empty. No data to process.")
        return

    try:
        df_original_system_data = pd.read_csv(
            original_system_data_path,
            usecols=[
                "agreement_id",
                "system_validity_from",  # Name as in mturk_tasks.csv
                "system_valid_to",  # Name as in mturk_tasks.csv
                "system_impacted_agreements_string",  # Name as in mturk_tasks.csv
            ],
        )
        # Rename for clarity when merging, to distinguish from human-corrected columns
        df_original_system_data.rename(
            columns={
                "system_validity_from": "system_validity_from_original",
                "system_valid_to": "system_valid_to_original",
                "system_impacted_agreements_string": "system_impacted_agreements_string_original",
            },
            inplace=True,
        )
    except FileNotFoundError:
        print(
            f"Error: Original system data (MTurk input) file not found at {original_system_data_path}."
        )
        print("This file is needed to retrieve original system values. Ensure path is correct.")
        return
    except KeyError as e:
        print(f"Error: Missing expected column in {original_system_data_path}: {e}")
        print(
            "Expected columns: agreement_id, system_validity_from, system_valid_to, system_impacted_agreements_string"
        )
        return

    processed_rows = []
    # Updated required columns from MTurk output based on hit_design.md and PRD 4.2.D
    required_mturk_cols = [
        "agreement_id",
        "human_validity_from_is_correct",
        "human_validity_from_corrected",  # Still collected
        # "human_validity_from_correction_justification", # Removed
        "human_valid_to_is_correct",
        "human_valid_to_corrected",  # Still collected
        # "human_valid_to_correction_justification", # Removed
        "human_impacted_agreements_is_correct",
        # "human_impacted_agreements_corrected_justified_json", # Removed
        "human_impacted_agreements_corrected_string",  # New field
        "annotation_notes",
    ]
    for col in required_mturk_cols:
        if col not in df_mturk_results.columns:
            print(
                f"Error: Required column '{col}' missing from MTurk results CSV: {mturk_results_csv_path}"
            )
            return

    for agreement_id, group in df_mturk_results.groupby("agreement_id"):
        consolidated = {"agreement_id": agreement_id}

        for field_is_correct in [
            "human_validity_from_is_correct",
            "human_valid_to_is_correct",
            "human_impacted_agreements_is_correct",
        ]:
            if group[field_is_correct].dtype == "object":
                # Attempt to convert string representations of boolean to actual boolean
                current_series = (
                    group[field_is_correct]
                    .astype(str)
                    .str.lower()
                    .replace(
                        {
                            "true": True,
                            "false": False,
                            "yes": True,
                            "no": False,
                            "1": True,
                            "0": False,
                            "1.0": True,
                            "0.0": False,
                        }
                    )
                )
                # Coerce to numeric, then boolean. Errors become NaN, then False.
                consolidated[field_is_correct] = (
                    pd.to_numeric(current_series, errors="coerce").fillna(0).astype(bool)
                )
            elif pd.api.types.is_numeric_dtype(group[field_is_correct]):
                consolidated[field_is_correct] = group[field_is_correct].astype(bool)
            else:  # Already boolean or some other type we hope Counter can handle
                # Fallback for unexpected types: try converting to string then to bool
                current_series_str = group[field_is_correct].astype(str).str.lower()
                bool_map = {
                    "true": True,
                    "false": False,
                    "yes": True,
                    "no": False,
                    "1": True,
                    "0": False,
                    "1.0": True,
                    "0.0": False,
                }
                current_series_bool = current_series_str.map(bool_map)
                consolidated[field_is_correct] = current_series_bool

            consolidated[field_is_correct] = get_consensus_value(consolidated[field_is_correct])

        if consolidated["human_validity_from_is_correct"] is False:
            vf_corrected_series = group["human_validity_from_corrected"].dropna()
            consolidated["human_validity_from_corrected"] = get_consensus_value(vf_corrected_series)
            if pd.notna(consolidated["human_validity_from_corrected"]) and not validate_date_format(
                consolidated["human_validity_from_corrected"]
            ):
                print(
                    f"Warning (AGR_ID: {agreement_id}): Invalid date format for human_validity_from_corrected: {consolidated['human_validity_from_corrected']}. Will use NA."
                )
                consolidated["human_validity_from_corrected"] = pd.NA
            # Justification removed
            # consolidated["human_validity_from_correction_justification"] = get_consensus_value(
            #     group["human_validity_from_correction_justification"].dropna()
            # )
        else:
            consolidated["human_validity_from_corrected"] = pd.NA
            # consolidated["human_validity_from_correction_justification"] = pd.NA # Removed

        if consolidated["human_valid_to_is_correct"] is False:
            vt_corrected_series = group["human_valid_to_corrected"].dropna()
            consolidated["human_valid_to_corrected"] = get_consensus_value(vt_corrected_series)
            if pd.notna(consolidated["human_valid_to_corrected"]) and not validate_date_format(
                consolidated["human_valid_to_corrected"]
            ):
                print(
                    f"Warning (AGR_ID: {agreement_id}): Invalid date format for human_valid_to_corrected: {consolidated['human_valid_to_corrected']}. Will use NA."
                )
                consolidated["human_valid_to_corrected"] = pd.NA
            # Justification removed
            # consolidated["human_valid_to_correction_justification"] = get_consensus_value(
            #     group["human_valid_to_correction_justification"].dropna()
            # )
        else:
            consolidated["human_valid_to_corrected"] = pd.NA
            # consolidated["human_valid_to_correction_justification"] = pd.NA # Removed

        if consolidated["human_impacted_agreements_is_correct"] is False:
            # Changed from _corrected_justified_json to _corrected_string
            ia_corrected_series = group[
                "human_impacted_agreements_corrected_string"  # Changed
            ].dropna()
            consolidated["human_impacted_agreements_corrected_string"] = (  # Changed
                get_consensus_value(ia_corrected_series)
            )
            if pd.notna(
                consolidated["human_impacted_agreements_corrected_string"]
            ) and not validate_comma_separated_quoted_strings(  # New validation function
                consolidated["human_impacted_agreements_corrected_string"]  # Changed
            ):
                print(
                    f"Warning (AGR_ID: {agreement_id}): Invalid format for human_impacted_agreements_corrected_string: {consolidated['human_impacted_agreements_corrected_string']}. Will use empty string."
                )
                consolidated["human_impacted_agreements_corrected_string"] = '""'  # Changed
        else:
            # If correct, no corrected string is expected. Store NA or empty string as appropriate.
            consolidated["human_impacted_agreements_corrected_string"] = pd.NA  # Changed

        notes_series = group["annotation_notes"].dropna()
        consolidated["annotation_notes"] = (
            "; ".join(notes_series) if not notes_series.empty else pd.NA
        )

        processed_rows.append(consolidated)

    if not processed_rows:
        print("No rows processed after consolidation. Annotations file will not be updated.")
        return

    df_processed_mturk = pd.DataFrame(processed_rows)
    # Merge with original system data to bring in system_..._original columns
    df_final = pd.merge(df_original_system_data, df_processed_mturk, on="agreement_id", how="right")

    # Rename for final output columns in annotations.csv - justifications are removed
    # df_final.rename(
    #     columns={
    #         "human_validity_from_correction_justification": "human_vf_correction_justification",
    #         "human_valid_to_correction_justification": "human_vt_correction_justification",
    #     },
    #     inplace=True,
    # )

    # Impacted agreements: human_impacted_agreements_corrected_string is already the final format.
    # No need for extract_titles or human_ia_corrected_justifications_json.
    # df_final["human_ia_corrected_justifications_json"] = df_final.apply(
    #     lambda row: (
    #         row["human_impacted_agreements_corrected_justified_json"]
    #         if row["human_impacted_agreements_is_correct"] is False
    #         else pd.NA
    #     ),
    #     axis=1,
    # )
    # df_final["human_impacted_agreements_corrected"] = df_final.apply(
    #     lambda row: (
    #         extract_titles(row["human_impacted_agreements_corrected_justified_json"])
    #         if row["human_impacted_agreements_is_correct"] is False
    #         else pd.NA
    #     ),
    #     axis=1,
    # )

    df_final["last_annotated_timestamp"] = pd.Timestamp.now()

    # Updated final annotation columns based on PRD and hit_design.md
    final_annotation_columns = [
        "agreement_id",
        "system_validity_from_original",  # Added: Original value shown to worker
        "system_valid_to_original",  # Added: Original value shown to worker
        "system_impacted_agreements_string_original",  # Added: Original value shown to worker
        "human_validity_from_is_correct",
        "human_validity_from_corrected",
        # "human_vf_correction_justification", # Removed
        "human_valid_to_is_correct",
        "human_valid_to_corrected",
        # "human_vt_correction_justification", # Removed
        "human_impacted_agreements_is_correct",
        "human_impacted_agreements_corrected_string",  # Changed from human_impacted_agreements_corrected
        # "human_ia_corrected_justifications_json", # Removed
        "annotation_notes",
        "last_annotated_timestamp",
    ]
    for col in final_annotation_columns:
        if col not in df_final.columns:
            df_final[col] = pd.NA
    df_final = df_final[final_annotation_columns]

    if os.path.exists(annotations_csv_path):
        try:
            df_existing_annotations = pd.read_csv(annotations_csv_path)
            if "agreement_id" not in df_existing_annotations.columns:
                print(
                    f"Error: 'agreement_id' not found in existing annotations file: {annotations_csv_path}. Cannot update."
                )
                # Save the processed data as a new file instead or append without checking for existing?
                # For now, let's save as new if existing is problematic.
                raise FileNotFoundError  # Treat as if it doesn't exist for simplicity here
            df_updated_annotations = pd.concat(
                [
                    df_existing_annotations[
                        ~df_existing_annotations["agreement_id"].isin(df_final["agreement_id"])
                    ],
                    df_final,
                ]
            ).reset_index(drop=True)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            print(
                f"Annotations CSV at {annotations_csv_path} not found or empty. Creating new file."
            )
            df_updated_annotations = df_final
        df_updated_annotations.to_csv(annotations_csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"Annotations CSV updated/created at: {annotations_csv_path}")
    else:
        df_final.to_csv(annotations_csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"New annotations CSV created at: {annotations_csv_path}")


if __name__ == "__main__":
    os.makedirs("data/mturk/output", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("data/mturk/input", exist_ok=True)  # Ensure dummy input dir exists

    dummy_mturk_input_path = "data/mturk/input/dummy_mturk_tasks_for_processing.csv"
    # Use the global MTURK_INPUT_PROCESSED_PATH for consistency
    if not os.path.exists(MTURK_INPUT_PROCESSED_PATH):
        print(f"Creating dummy MTurk input for processing: {MTURK_INPUT_PROCESSED_PATH}")
        dummy_input_data = pd.DataFrame(
            [
                {
                    "agreement_id": "AGR001",
                    "system_validity_from": "2023/01/01",  # Name as in data_prep output
                    "system_valid_to": "2023/12/31",  # Name as in data_prep output
                    "system_impacted_agreements_string": '"SubA", "SubB"',  # Name as in data_prep output
                },
                {
                    "agreement_id": "AGR002",
                    "system_validity_from": "2024/XX/XX",
                    "system_valid_to": "Indefinite",
                    "system_impacted_agreements_string": '""',  # Empty string
                },
            ]
        )
        dummy_input_data.to_csv(MTURK_INPUT_PROCESSED_PATH, index=False)

    if not os.path.exists(MTURK_OUTPUT_RAW_CSV_PATH):
        print(f"Creating dummy MTurk results file: {MTURK_OUTPUT_RAW_CSV_PATH}")
        dummy_results_data = [
            {  # Worker 1 for AGR001
                "agreement_id": "AGR001",
                "human_validity_from_is_correct": "false",  # Stored as string from MTurk
                "human_validity_from_corrected": "2023/01/02",
                # "human_validity_from_correction_justification": "Off by one day.", # Removed
                "human_valid_to_is_correct": "true",
                "human_valid_to_corrected": pd.NA,  # Correctly NA if is_correct is true
                # "human_valid_to_correction_justification": pd.NA, # Removed
                "human_impacted_agreements_is_correct": "false",
                # "human_impacted_agreements_corrected_justified_json": ..., # Removed
                "human_impacted_agreements_corrected_string": '"SubA Corrected", "NewSub"',  # New field
                "annotation_notes": "Worker 1 notes for AGR001",
            },
            {  # Worker 2 for AGR001 - different opinions
                "agreement_id": "AGR001",
                "human_validity_from_is_correct": "true",
                "human_validity_from_corrected": pd.NA,
                # "human_validity_from_correction_justification": pd.NA, # Removed
                "human_valid_to_is_correct": "true",
                "human_valid_to_corrected": pd.NA,
                # "human_valid_to_correction_justification": pd.NA, # Removed
                "human_impacted_agreements_is_correct": "false",
                "human_impacted_agreements_corrected_string": '"SubA Corrected"',  # Different correction
                "annotation_notes": "Worker 2 notes for AGR001",
            },
            {  # Worker 1 for AGR002
                "agreement_id": "AGR002",
                "human_validity_from_is_correct": "true",
                "human_validity_from_corrected": pd.NA,
                # "human_validity_from_correction_justification": pd.NA, # Removed
                "human_valid_to_is_correct": "false",
                "human_valid_to_corrected": "2025/01/01",
                # "human_valid_to_correction_justification": "End date found.", # Removed
                "human_impacted_agreements_is_correct": "true",
                "human_impacted_agreements_corrected_string": pd.NA,  # Correctly NA
                "annotation_notes": "All good for AGR002",
            },
        ]
        dummy_results = pd.DataFrame(dummy_results_data)
        # Ensure boolean fields are actually boolean if True/False, or strings for the test CSV for robustness
        for bool_col in [
            "human_validity_from_is_correct",
            "human_valid_to_is_correct",
            "human_impacted_agreements_is_correct",
        ]:
            if bool_col in dummy_results.columns:
                dummy_results[bool_col] = dummy_results[bool_col].astype(
                    str
                )  # Store as string 'true'/'false' to test parsing
        dummy_results.to_csv(MTURK_OUTPUT_RAW_CSV_PATH, index=False)

    print(
        "Running result processing script. Ensure input files exist or dummy files will be created:"
    )
    print(f"  MTurk Raw Results: {MTURK_OUTPUT_RAW_CSV_PATH}")
    print(f"  Original System Data (from MTurk input): {MTURK_INPUT_PROCESSED_PATH}")
    print(f"  Output Annotations CSV: {ANNOTATION_FILE_PATH}")

    process_mturk_results(
        MTURK_OUTPUT_RAW_CSV_PATH, ANNOTATION_FILE_PATH, MTURK_INPUT_PROCESSED_PATH
    )

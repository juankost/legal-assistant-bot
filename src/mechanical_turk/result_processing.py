import csv
import json
import pandas as pd
import os
from collections import Counter

# Assumptions:
# ANNOTATION_FILE_PATH: Path to the main annotation CSV file that needs to be updated.
# Example: 'data/processed/annotations.csv' (consistent with PRD naming and README structure)
# MTURK_OUTPUT_CSV_PATH: Path to the CSV file downloaded from MTurk containing worker responses.
# Example: 'data/mturk/output/mturk_results.csv'

ANNOTATION_FILE_PATH = "data/processed/annotations.csv"  # Placeholder
MTURK_OUTPUT_RAW_CSV_PATH = (
    "data/mturk/output/mturk_results_raw.csv"  # Placeholder for raw MTurk output
)


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


def validate_impacted_agreements_json(json_str):
    """Validates if the string is a JSON list of objects with specific keys."""
    if not isinstance(json_str, str):
        return False  # Must be a string to be valid JSON text
    try:
        data = json.loads(json_str)
        if not isinstance(data, list):
            return False
        for item in data:
            if (
                not isinstance(item, dict)
                or "impacted_agreement_title" not in item
                or "justification" not in item
            ):
                return False
        return True
    except json.JSONDecodeError:
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
    original_llm_data_path,  # Path to the data sent to MTurk, to retrieve original LLM values if needed
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
            "Expected columns (example): agreement_id, human_validity_from_is_correct, human_validity_from_corrected, ..."
        )
        return

    if df_mturk_results.empty:
        print("MTurk results CSV is empty. No data to process.")
        return

    try:
        df_original_llm_data = pd.read_csv(
            original_llm_data_path,
            usecols=[
                "agreement_id",
                "llm_validity_from",
                "llm_valid_to",
                "llm_impacted_agreements_justified_json",
            ],
        )
        df_original_llm_data.rename(
            columns={
                "llm_impacted_agreements_justified_json": "original_llm_impacted_agreements_justified_json"
            },
            inplace=True,
        )
    except FileNotFoundError:
        print(f"Error: Original LLM data (MTurk input) file not found at {original_llm_data_path}.")
        print("This file is needed to retrieve original LLM values. Ensure path is correct.")
        return
    except KeyError as e:
        print(f"Error: Missing expected column in {original_llm_data_path}: {e}")
        return

    processed_rows = []
    required_mturk_cols = [
        "agreement_id",
        "human_validity_from_is_correct",
        "human_validity_from_corrected",
        "human_validity_from_correction_justification",
        "human_valid_to_is_correct",
        "human_valid_to_corrected",
        "human_valid_to_correction_justification",
        "human_impacted_agreements_is_correct",
        "human_impacted_agreements_corrected_justified_json",
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
                consolidated[field_is_correct] = group[field_is_correct]
            consolidated[field_is_correct] = get_consensus_value(consolidated[field_is_correct])

        if consolidated["human_validity_from_is_correct"] is False:
            vf_corrected_series = group["human_validity_from_corrected"].dropna()
            consolidated["human_validity_from_corrected"] = get_consensus_value(vf_corrected_series)
            if not validate_date_format(consolidated["human_validity_from_corrected"]):
                print(
                    f"Warning (AGR_ID: {agreement_id}): Invalid date format for human_validity_from_corrected: {consolidated['human_validity_from_corrected']}. Will use NA."
                )
                consolidated["human_validity_from_corrected"] = pd.NA
            consolidated["human_validity_from_correction_justification"] = get_consensus_value(
                group["human_validity_from_correction_justification"].dropna()
            )
        else:
            consolidated["human_validity_from_corrected"] = pd.NA
            consolidated["human_validity_from_correction_justification"] = pd.NA

        if consolidated["human_valid_to_is_correct"] is False:
            vt_corrected_series = group["human_valid_to_corrected"].dropna()
            consolidated["human_valid_to_corrected"] = get_consensus_value(vt_corrected_series)
            if not validate_date_format(consolidated["human_valid_to_corrected"]):
                print(
                    f"Warning (AGR_ID: {agreement_id}): Invalid date format for human_valid_to_corrected: {consolidated['human_valid_to_corrected']}. Will use NA."
                )
                consolidated["human_valid_to_corrected"] = pd.NA
            consolidated["human_valid_to_correction_justification"] = get_consensus_value(
                group["human_valid_to_correction_justification"].dropna()
            )
        else:
            consolidated["human_valid_to_corrected"] = pd.NA
            consolidated["human_valid_to_correction_justification"] = pd.NA

        if consolidated["human_impacted_agreements_is_correct"] is False:
            ia_corrected_series = group[
                "human_impacted_agreements_corrected_justified_json"
            ].dropna()
            consolidated["human_impacted_agreements_corrected_justified_json"] = (
                get_consensus_value(ia_corrected_series)
            )
            if not validate_impacted_agreements_json(
                consolidated["human_impacted_agreements_corrected_justified_json"]
            ):
                print(
                    f"Warning (AGR_ID: {agreement_id}): Invalid JSON for human_impacted_agreements_corrected_justified_json. Will use empty list."
                )
                consolidated["human_impacted_agreements_corrected_justified_json"] = "[]"
        else:
            consolidated["human_impacted_agreements_corrected_justified_json"] = pd.NA

        notes_series = group["annotation_notes"].dropna()
        consolidated["annotation_notes"] = (
            "; ".join(notes_series) if not notes_series.empty else pd.NA
        )

        processed_rows.append(consolidated)

    if not processed_rows:
        print("No rows processed after consolidation. Annotations file will not be updated.")
        return

    df_processed_mturk = pd.DataFrame(processed_rows)
    df_final = pd.merge(df_original_llm_data, df_processed_mturk, on="agreement_id", how="right")

    df_final.rename(
        columns={
            "human_validity_from_correction_justification": "human_vf_correction_justification",
            "human_valid_to_correction_justification": "human_vt_correction_justification",
        },
        inplace=True,
    )

    def extract_titles(json_str):
        if pd.isna(json_str) or not isinstance(json_str, str) or not json_str:
            return pd.NA
        try:
            items = json.loads(json_str)
            if not isinstance(items, list):
                return pd.NA  # Expect a list
            return json.dumps(
                [
                    item.get("impacted_agreement_title")
                    for item in items
                    if isinstance(item, dict) and "impacted_agreement_title" in item
                ]
            )
        except (json.JSONDecodeError, TypeError):
            return pd.NA

    df_final["human_ia_corrected_justifications_json"] = df_final.apply(
        lambda row: (
            row["human_impacted_agreements_corrected_justified_json"]
            if row["human_impacted_agreements_is_correct"] is False
            else pd.NA
        ),
        axis=1,
    )
    df_final["human_impacted_agreements_corrected"] = df_final.apply(
        lambda row: (
            extract_titles(row["human_impacted_agreements_corrected_justified_json"])
            if row["human_impacted_agreements_is_correct"] is False
            else pd.NA
        ),
        axis=1,
    )

    df_final["last_annotated_timestamp"] = pd.Timestamp.now()

    final_annotation_columns = [
        "agreement_id",
        "llm_validity_from",
        "llm_valid_to",
        "original_llm_impacted_agreements_justified_json",
        "human_validity_from_is_correct",
        "human_validity_from_corrected",
        "human_vf_correction_justification",
        "human_valid_to_is_correct",
        "human_valid_to_corrected",
        "human_vt_correction_justification",
        "human_impacted_agreements_is_correct",
        "human_impacted_agreements_corrected",
        "human_ia_corrected_justifications_json",
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
    if not os.path.exists(dummy_mturk_input_path):
        print(f"Creating dummy MTurk input for processing: {dummy_mturk_input_path}")
        dummy_input_data = pd.DataFrame(
            [
                {
                    "agreement_id": "AGR001",
                    "llm_validity_from": "2023/01/01",
                    "llm_valid_to": "2023/12/31",
                    "llm_impacted_agreements_justified_json": json.dumps(
                        [{"impacted_agreement_title": "SubA", "justification": "LLM just for SubA"}]
                    ),
                },
                {
                    "agreement_id": "AGR002",
                    "llm_validity_from": "2024/XX/XX",
                    "llm_valid_to": "Indefinite",
                    "llm_impacted_agreements_justified_json": json.dumps([]),
                },
            ]
        )
        dummy_input_data.to_csv(dummy_mturk_input_path, index=False)

    if not os.path.exists(MTURK_OUTPUT_RAW_CSV_PATH):
        print(f"Creating dummy MTurk results file: {MTURK_OUTPUT_RAW_CSV_PATH}")
        dummy_results_data = [
            {
                "agreement_id": "AGR001",
                "human_validity_from_is_correct": "false",
                "human_validity_from_corrected": "2023/01/02",
                "human_validity_from_correction_justification": "Off by one day.",
                "human_valid_to_is_correct": "true",
                "human_valid_to_corrected": pd.NA,
                "human_valid_to_correction_justification": pd.NA,
                "human_impacted_agreements_is_correct": "false",
                "human_impacted_agreements_corrected_justified_json": json.dumps(
                    [
                        {
                            "impacted_agreement_title": "SubA",
                            "justification": "Corrected justification for SubA",
                        },
                        {"impacted_agreement_title": "SubB", "justification": "Added SubB"},
                    ]
                ),
                "annotation_notes": "Worker 1 notes for AGR001",
            },
            {
                "agreement_id": "AGR001",
                "human_validity_from_is_correct": "true",
                "human_validity_from_corrected": pd.NA,
                "human_validity_from_correction_justification": pd.NA,
                "human_valid_to_is_correct": "true",
                "human_valid_to_corrected": pd.NA,
                "human_valid_to_correction_justification": pd.NA,
                "human_impacted_agreements_is_correct": "false",
                "human_impacted_agreements_corrected_justified_json": json.dumps(
                    [
                        {
                            "impacted_agreement_title": "SubA",
                            "justification": "Corrected again for SubA",
                        }
                    ]
                ),
                "annotation_notes": "Worker 2 notes for AGR001",
            },
            {
                "agreement_id": "AGR002",
                "human_validity_from_is_correct": "true",
                "human_validity_from_corrected": pd.NA,
                "human_validity_from_correction_justification": pd.NA,
                "human_valid_to_is_correct": "false",
                "human_valid_to_corrected": "2025/01/01",
                "human_valid_to_correction_justification": "End date found.",
                "human_impacted_agreements_is_correct": "true",
                "human_impacted_agreements_corrected_justified_json": pd.NA,
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
    print(f"  Original LLM Data (from MTurk input): {dummy_mturk_input_path}")
    print(f"  Output Annotations CSV: {ANNOTATION_FILE_PATH}")

    process_mturk_results(MTURK_OUTPUT_RAW_CSV_PATH, ANNOTATION_FILE_PATH, dummy_mturk_input_path)

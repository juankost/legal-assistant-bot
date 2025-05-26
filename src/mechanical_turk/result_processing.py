import csv
import pandas as pd
import os
from collections import Counter
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.max_rows", None)

# MTURK_OUTPUT_RAW schema:
# "HITId","HITTypeId","Title","Description","Keywords","Reward","CreationTime",
# "MaxAssignments","RequesterAnnotation","AssignmentDurationInSeconds",
# "AutoApprovalDelayInSeconds","Expiration","NumberOfSimilarHITs","LifetimeInSeconds",
# "AssignmentId","WorkerId","AssignmentStatus","AcceptTime","SubmitTime",
# "AutoApprovalTime","ApprovalTime","RejectionTime","RequesterFeedback",
# "WorkTimeInSeconds","LifetimeApprovalRate","Last30DaysApprovalRate",
# "Last7DaysApprovalRate","Input.radioName","Input.agreement_id",
# "Input.agreement_title","Input.agreement_text_url","Input.system_validity_from",
# "Input.system_valid_to","Input.system_impacted_agreements_strin","Answer.agreement_id",
# "Answer.annotation_notes","Answer.human_impacted_agreements_corrected_string",
# "Answer.human_impacted_agreements_is_correct","Answer.human_valid_to_corrected",
# "Answer.human_valid_to_is_correct","Answer.human_validity_from_corrected",
# "Answer.human_validity_from_is_correct","Approve","Reject"


DATA_DIR = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data"
ANNOTATION_FILE_PATH = os.path.join(DATA_DIR, "agreement_validity.csv")
MTURK_OUTPUT_RAW_CSV_PATH = os.path.join(DATA_DIR, "mturk", "output", "mturk_results_raw.csv")


def validate_date_format(date_str):
    """Validates if the date string matches YYYY/MM/DD, YYYY/MM/XX, YYYY/XX/XX, or Not Specified."""
    if not isinstance(date_str, str):
        return False
    if date_str in ["Not Specified", "Not specified", "not specified"]:
        return True

    parts = date_str.split("/")
    if len(parts) == 3:
        year, month, day = parts
        if (
            len(year) == 4
            and year.isdigit()
            and (len(month) == 2 and (month.isdigit() or month == "XX") and int(month) <= 12)
            and (len(day) == 2 and (day.isdigit() or day == "XX") and int(day) <= 31)
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
    if value_str == '""':
        return True
    if not value_str:
        return False

    # Check if it is a comma-separated list of titles in double quotes
    values_list = value_str.split(
        ","
    )  # each list item should then be validated as a double quoted string
    for value in values_list:
        if not value.startswith('"') or not value.endswith('"'):
            return False
    return True


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
):
    """
    Processes results from MTurk, performs validation, consolidation,
    and updates the main annotation file.
    """
    df_mturk_results = pd.read_csv(mturk_results_csv_path)

    #########################################################
    ### Get the columns that I want from the mturk results ###
    #########################################################
    mturk_rename_dict = {
        "HITId": "hit_id",
        "Input.agreement_id": "agreement_id",
        "Answer.human_validity_from_is_correct": "human_validity_from_is_correct",
        "Answer.human_validity_from_corrected": "human_validity_from_corrected",
        "Input.system_validity_from": "system_validity_from",
        "Input.system_valid_to": "system_valid_to",
        "Input.system_impacted_agreements_strin": "system_impacted_agreements_string",
        "Answer.human_valid_to_is_correct": "human_valid_to_is_correct",
        "Answer.human_valid_to_corrected": "human_valid_to_corrected",
        "Answer.human_impacted_agreements_is_correct": "human_impacted_agreements_is_correct",
        "Answer.human_impacted_agreements_corrected_string": "human_impacted_agreements_corrected_string",  # noqa
    }
    df_mturk_results.rename(columns=mturk_rename_dict, inplace=True)
    df_mturk_results = df_mturk_results[mturk_rename_dict.values()]

    #########################################
    ### Validate the answers for each row ###
    #########################################
    df_mturk_results["human_validity_from_is_correct"] = df_mturk_results[
        "human_validity_from_is_correct"
    ].astype(bool)
    df_mturk_results["human_valid_to_is_correct"] = df_mturk_results[
        "human_valid_to_is_correct"
    ].astype(bool)
    df_mturk_results["human_impacted_agreements_is_correct"] = df_mturk_results[
        "human_impacted_agreements_is_correct"
    ].astype(bool)

    human_system_align_cond = (
        df_mturk_results["human_validity_from_is_correct"]
        & df_mturk_results["human_valid_to_is_correct"]
        & df_mturk_results["human_impacted_agreements_is_correct"]
    )
    human_correction_valid_cond = (
        df_mturk_results["human_validity_from_corrected"].apply(lambda x: validate_date_format(x))
        & df_mturk_results["human_valid_to_corrected"].apply(lambda x: validate_date_format(x))
        & df_mturk_results["human_impacted_agreements_corrected_string"].apply(
            lambda x: validate_comma_separated_quoted_strings(x)
        )
    )
    df_mturk_results["valid_row"] = human_system_align_cond | human_correction_valid_cond
    df_mturk_results["human_system_align"] = human_system_align_cond
    df_mturk_results["human_correction_valid"] = human_correction_valid_cond

    # Keep only valid rows
    print(f"There are {df_mturk_results['valid_row'].sum()}/{len(df_mturk_results)} valid rows.")
    # for index, row in df_mturk_results[df_mturk_results["valid_row"] == False].iterrows():
    #     print("Row was not valid!!")
    #     print(f"({index}, {row.to_dict()})")
    df_mturk_results = df_mturk_results[df_mturk_results["valid_row"]]

    # combine the system extracted and the human corrected values into single columns
    df_mturk_results["valid_from"] = np.where(
        df_mturk_results["human_validity_from_is_correct"],
        df_mturk_results["system_validity_from"],
        df_mturk_results["human_validity_from_corrected"],
    )
    df_mturk_results["valid_to"] = np.where(
        df_mturk_results["human_valid_to_is_correct"],
        df_mturk_results["system_valid_to"],
        df_mturk_results["human_valid_to_corrected"],
    )
    df_mturk_results["impacted_agreements"] = np.where(
        df_mturk_results["human_impacted_agreements_is_correct"],
        df_mturk_results["system_impacted_agreements_string"],
        df_mturk_results["human_impacted_agreements_corrected_string"],
    )

    # Delete now the columns of the system extracted values and the human corrected values
    df_mturk_results.drop(
        columns=[
            "human_validity_from_corrected",
            "human_valid_to_corrected",
            "human_impacted_agreements_corrected_string",
            "system_validity_from",
            "system_valid_to",
            "system_impacted_agreements_string",
            "human_impacted_agreements_is_correct",
            "human_validity_from_is_correct",
            "human_valid_to_is_correct",
            "human_system_align",
            "human_correction_valid",
            "valid_row",
        ],
        inplace=True,
    )

    # Now for each agreement id, group by the unique value for each of the fields (valid_from, valid_to, impacted_agreements)
    # and get the majority vote for each of the fields
    def get_majority_vote_option(df_group):
        valid_from_values = df_group["valid_from"].values.tolist()
        valid_to_values = df_group["valid_to"].values.tolist()
        impacted_agreements_values = df_group["impacted_agreements"].values.tolist()
        valid_from_counts = Counter(valid_from_values)
        valid_to_counts = Counter(valid_to_values)
        impacted_agreements_counts = Counter(impacted_agreements_values)

        # TODO: What if there are two equally most common?
        valid_from_most_common = valid_from_counts.most_common()[0][0]
        valid_to_most_common = valid_to_counts.most_common()[0][0]
        impacted_agreements_most_common = impacted_agreements_counts.most_common()[0][0]

        output_df = pd.DataFrame(
            {
                "mturk_hit_id": [df_group.iloc[0]["hit_id"]],
                "agreement_id": [df_group.iloc[0]["agreement_id"]],
                "mturk_valid_from": [valid_from_most_common],
                "mturk_valid_from_consensus_share": [
                    valid_from_counts.most_common()[0][1] / len(df_group)
                ],
                "mturk_valid_to": [valid_to_most_common],
                "mturk_valid_to_consensus_share": [
                    valid_to_counts.most_common()[0][1] / len(df_group)
                ],
                "mturk_impacted_agreements": [impacted_agreements_most_common],
                "mturk_impacted_agreements_consensus_share": [
                    impacted_agreements_counts.most_common()[0][1] / len(df_group)
                ],
            }
        )

        return output_df

    df_mturk_results = (
        df_mturk_results.groupby(["agreement_id", "hit_id"], as_index=False)
        .apply(get_majority_vote_option)
        .reset_index()
    ).drop(columns=["level_1", "level_0"])

    # Write the results to the annotation CSV file
    annotation_df = pd.read_csv(annotations_csv_path)
    if any(["mturk_" in x for x in annotation_df.columns]):
        annotation_df = annotation_df[
            ["agreement_id", "agreement_title", "validity_from", "valid_to", "impacted_agreements"]
        ]

    enriched_annotation_df = pd.merge(
        annotation_df, df_mturk_results, on="agreement_id", how="left"
    )
    print(enriched_annotation_df.columns)
    enriched_annotation_df.to_csv(annotations_csv_path, index=False)
    return


if __name__ == "__main__":
    print(f"  MTurk Raw Results: {MTURK_OUTPUT_RAW_CSV_PATH}")
    print(f"  Output Annotations CSV: {ANNOTATION_FILE_PATH}")
    process_mturk_results(MTURK_OUTPUT_RAW_CSV_PATH, ANNOTATION_FILE_PATH)

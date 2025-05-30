AGREEMENT_VALIDITY_PROMPT = """
You are a legal expert specializing in analyzing legal agreements and contracts. I need you to 
determine the validity period and relationships between documents for the following agreement:

AGREEMENT TITLE: {title}
AGREEMENT INFO: {info}

I'll provide the beginning text of the agreement, and a list of all other agreement titles for reference.

AGREEMENT TEXT (first part):
{text}

ALL AGREEMENT TITLES IN COLLECTION:
{all_titles}

Please analyze the information and extract:

1. VALID_FROM: When does the agreement come into effect? (in YYYY/MM/DD format)
   - Look for dates in the agreement text or title
   - Look for phrases like "effective date", "commencement date", etc.
   - If a year appears in the title, it likely indicates when the agreement was reached

2. VALID_TO: When does the agreement expire? (in YYYY/MM/DD format)
   - Look for mentions of expiration, termination, or end dates
   - If not explicitly mentioned, leave as empty string (assumed to be still valid)

3. IMPACTED_AGREEMENTS: Which agreements does this document modify or impact?
   - If this is a memorandum of agreement, it likely modifies an existing agreement
   - Look for mentions of previous agreements or amendments or agreed changes to existing agreements or agreements incorporated
   - Use the provided list of all agreement titles to match exact names
   - Return an empty list if no agreements are impacted

IMPORTANT NOTES:
- Memorandums don't fully invalidate original agreements; they only introduce changes
- When a memorandum modifies an agreement, the original agreement is valid until the 
  memorandum's effective date
- Only return agreements that are DIRECTLY impacted, not agreements that might be related topically
- Return dates in YYYY/MM/DD format exactly
- If a date component is unknown, use "XX" (e.g., "2020/XX/XX" if only year is known)

Provide your analysis in a structured JSON format as follows:
{{
  "valid_from": "YYYY/MM/DD",
  "valid_to": "YYYY/MM/DD",
  "impacted_agreements": ["Full Agreement Title 1", "Full Agreement Title 2"]
}}
"""

AGREEMENT_SUMMARY_PROMPT = """\
You are a helpful assistant that summarizes legal agreements.
Analyze the following agreement text and provide a summary highlighting the main purpose and scope of the agreement.

Agreement Title: {title}
Agreement Text (first 10000 characters):
{text}

Summary:
"""

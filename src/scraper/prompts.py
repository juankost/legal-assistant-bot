PROMPT_EXTRACT_CATEGORY_URLS_STRUCT = """
Analyze the provided HTML content from a webpage listing various contract categories. It implements
a navigation list with categories and subcategories. Identify all the categories and subcategories
and their URLs. From the navigation list html, extract the hierarchical structure of the categories,
subcategories and their URLs.

Present the results strictly as a JSON list of objects. Each object should have
the following keys:
- "category_name": The descriptive text of the link of the category (for the subcategories, this will be the parent category).
- "subcategory_name": The descriptive text of the link (if it is a subcategory, otherwise it is an empty string).
- "url": The full URL of the category or subcategory.

Example JSON Output:
```json
[
  {
    "category_name": "Category 1",
    "subcategory_name": "",
    "url": "https://www.sagaftra.org/production-center/contract/813/getting-started"
  },
  {
    "category_name": "Category 2",
    "subcategory_name": "Subcategory 1",
    "url": "https://www.sagaftra.org/production-center/contract/814/subcategory-1/getting-started"
  },
  {
    "category_name": "Category 2",
    "subcategory_name": "Subcategory 2",
    "url": "https://www.sagaftra.org/production-center/contract/814/subcategory-2/getting-started"
  }
]
```
"""


PROMPT_EXTRACT_PDF_URLS_STRUCT = """
Analyze the provided HTML content from a specific contract agreement page.
Identify all hyperlink (`<a>`) tags that link directly to a PDF document
(i.e., the `href` attribute ends with '.pdf').

For each PDF link found, extract:
1. The descriptive title or name of the agreement (usually the link text).
2. The full URL of the PDF document from the `href` attribute.
3. Any other information about the agreement that you can extract from the page. Otherwise, this field should be an empty string.

Present the results strictly as a JSON list of objects. Each object should have
the following keys:
- "agreement_title": The descriptive title or name of the agreement.
- "agreement_url": The full URL of the PDF.
- "agreement_info": Any other information about the agreement that you can extract from the page. Otherwise, this field should be an empty string.

Do not include any introductory text, explanations, or markdown formatting
outside of the JSON list itself. Ensure URLs are complete and absolute.
If the HTML contains relative URLs, resolve them based on the likely base URL
(assume sagaftra.org if needed, but prefer absolute URLs if present in the HTML).

Example JSON Output:
```json
[
  {
    "agreement_title": "Example Agreement Form",
    "agreement_url": "https://www.sagaftra.org/files/example_agreement.pdf",
    "agreement_info": "Example PDF."
  },
  {
    "agreement_title": "Another Form",
    "agreement_url": "https://www.sagaftra.org/files/another_form.pdf",
    "agreement_info": "Valid until 2025."
  },
  {
    "agreement_title": "Agreement 3",
    "agreement_url": "https://www.sagaftra.org/files/agreement_3.pdf",
    "agreement_info": ""
  }
]
```
"""

import requests
import google.genai as genai
import tqdm
import os
import pandas as pd
import json
from dotenv import load_dotenv
import logging
import sys
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scraper.prompts import (
    PROMPT_EXTRACT_CATEGORY_URLS_STRUCT,
    PROMPT_EXTRACT_PDF_URLS_STRUCT,
)

DATA_DIR = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    logging.error("GEMINI_API_KEY not found in environment variables.")
    logging.error("Please create a .env file with GEMINI_API_KEY=YOUR_API_KEY")
    exit()

# Instantiate the client using the API key
client = genai.Client(api_key=api_key)
generation_config = genai.types.GenerateContentConfig(temperature=0.1)


def get_html(url):
    """Fetches HTML content from a given URL."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        logging.info(f"Successfully fetched HTML from {url}")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching {url}: {e}")
        return None


def call_gemini(prompt, model_name="gemini-2.5-pro-preview-03-25", response_schema=None):
    """Calls the Gemini API with a specific prompt and HTML content."""
    try:
        logging.info(f"--- Calling Gemini ({model_name}) ---")

        if response_schema:
            config = genai.types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=response_schema,
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            if response.candidates and response.candidates[0].content.parts:
                json_response = json.loads(response.text)
                return json_response
            else:
                logging.error(
                    "LLM response was empty or did not contain the expected content parts for structured output."
                )
        else:
            config = genai.types.GenerateContentConfig(temperature=0.1)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            if response.candidates:
                # breakpoint()
                logging.info("Received response from Gemini.")
                return response.candidates[0].content.parts[0].text
            else:
                logging.warning("Gemini response was empty or blocked.")
                return None

    except Exception as e:
        logging.error(f"Error calling Gemini API: {e}")
        return None


def extract_category_urls_from_html(html_content, model_name="gemini-2.5-pro-preview-03-25"):
    """
    Heuristic function to extract category URLs from HTML content.
    Extract the navList element, then use an LLM to extract the categories and subcategories
    with their names and URLs
    If the NavList element is not found, we simply scrape all the links in the page that
    end with "getting-started" and try to heuristically extract the categories and subcategories.

    Args:
        html_content: The HTML content of the page to extract the categories and subcategories from
        model_name: The name of the Gemini model to use for the LLM
    Returns:
        A pandas DataFrame with the categories and subcategories and their names and URLs
    """

    soup = BeautifulSoup(html_content, "html.parser")

    navList_element = soup.find("div", class_="navList")
    if not navList_element:
        logging.error("No navList element found in the HTML content.")

        category_urls = []
        for link in navList_element.find_all("a", href=True):
            href = link["href"]
            if href.endswith("getting-started"):
                text = link.text.strip()
                child_div = link.find_next("div")
                if child_div and child_div.find_next("ul"):
                    all_child_nodes = child_div.find_all("a", href=True)
                    for child_node in all_child_nodes:
                        child_href = child_node["href"]
                        if child_href.endswith("getting-started"):
                            child_text = child_node.text.strip()
                            category_urls.append(
                                {
                                    "category_name": text,
                                    "subcategory_name": child_text,
                                    "url": child_href,
                                }
                            )
                    # Save also the parent category
                    category_urls.append(
                        {"category_name": text, "subcategory_name": "", "url": href}
                    )
            else:
                # Did not find child node --> we can already be at a subcategory or this category
                # does not have any subcategories
                category_urls.append({"category_name": text, "subcategory_name": "", "url": href})

        # Need to remove the duplicates (i.e. the subcategories were counted as child nodes, and
        data = pd.DataFrame(category_urls)
        subcategory_data = data[data["subcategory_name"] != ""]
        category_data = data[data["subcategory_name"] == ""]

        # Filter out the subcategories that are also in the category_data
        subcategory_urls_set = set(subcategory_data["url"])
        filtered_category_data = category_data[~category_data["url"].isin(subcategory_urls_set)]
        combined_filtered_data = pd.concat([filtered_category_data, subcategory_data])
        return combined_filtered_data
    else:
        prompt = f"{PROMPT_EXTRACT_CATEGORY_URLS_STRUCT}\\n\\nHTML Content:\\n```html\\n{html_content}\\n```"  # noqa
        category_schema = genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                properties={
                    "category_name": genai.types.Schema(type=genai.types.Type.STRING),
                    "subcategory_name": genai.types.Schema(type=genai.types.Type.STRING),
                    "url": genai.types.Schema(type=genai.types.Type.STRING),
                },
                required=["category_name", "subcategory_name", "url"],
            ),
        )
        response = call_gemini(prompt, model_name=model_name, response_schema=category_schema)
        print(response)
        df = pd.DataFrame(response)
        df = df[["category_name", "subcategory_name", "url"]]
        return df


def extract_agreements_metadata():
    """
    This function scrapes from the base URL the categories and subcategories and then
    for each category and subcategory, it scrapes the agreements metadata, including the
    title and the URL of the PDF agreement.

    It saves the data in a CSV file: data/raw/agreement_metadata.csv
    """
    base_url = "https://www.sagaftra.org/production-center/contract/813/getting-started"
    domain = "https://www.sagaftra.org"

    if not os.path.exists(f"{DATA_DIR}/raw/category_information.csv"):
        base_html = get_html(base_url)
        if not base_html:
            raise Exception("Failed to fetch base HTML. Exiting.")

        category_information = extract_category_urls_from_html(base_html)
        category_information["url"] = category_information["url"].apply(
            lambda x: domain + x if x.startswith("/") else x
        )
        category_information.to_csv(f"{DATA_DIR}/raw/category_information.csv", index=False)
    else:
        category_information = pd.read_csv(f"{DATA_DIR}/raw/category_information.csv")

    all_agreements_data = []
    for index, row in category_information.iterrows():
        category_name = row["category_name"]
        subcategory_name = row["subcategory_name"]
        url_link = row["url"]

        if "getting-started" not in url_link:
            logging.warning(f"  Skipping URL (does not contain 'getting-started'): {url_link}")
            continue

        agreement_page_url = url_link.replace("/getting-started", "/agreement/document")
        agreement_html = get_html(agreement_page_url)
        if not agreement_html:
            logging.warning(
                f"Failed to fetch agreement page HTML for {agreement_page_url}. "
                "Skipping category."
            )
            all_agreements_data.append(
                {
                    "category": category_name,
                    "subcategory": subcategory_name,
                    "url": url_link,
                    "agreement_title": "",
                    "agreement_url": "",
                    "agreement_text": "",
                }
            )
            continue

        # Extract the PDF URLs
        query = f"{PROMPT_EXTRACT_PDF_URLS_STRUCT}\\n\\nHTML Content:\\n```html\\n{agreement_html}\\n```"
        response_schema = genai.types.Schema(
            type=genai.types.Type.ARRAY,
            items=genai.types.Schema(
                type=genai.types.Type.OBJECT,
                properties={
                    "agreement_title": genai.types.Schema(type=genai.types.Type.STRING),
                    "agreement_url": genai.types.Schema(type=genai.types.Type.STRING),
                    "agreement_info": genai.types.Schema(type=genai.types.Type.STRING),
                },
                required=["agreement_title", "agreement_url", "agreement_info"],
            ),
        )
        response = call_gemini(
            query, response_schema=response_schema, model_name="gemini-2.0-flash"
        )
        agreements_data = pd.DataFrame(response)
        agreements_data["category"] = category_name
        agreements_data["subcategory"] = subcategory_name
        agreements_data["url"] = url_link
        all_agreements_data.append(agreements_data)

    # Combine all collected data
    all_agreements_data = pd.concat(all_agreements_data)

    # Add agreement_id column
    all_agreements_data["agreement_id"] = range(len(all_agreements_data))

    # Save to CSV
    output_path = f"{DATA_DIR}/raw/agreement_metadata.csv"
    all_agreements_data.to_csv(output_path, index=False)
    logging.info(f"Saved {len(all_agreements_data)} agreements to {output_path}")

    return all_agreements_data


def download_agreements(agreement_metadata_path):
    """
    Download the agreements from the URLs in the agreement_metadata DataFrame.
    Update the agreement_metadata.csv file with the path to the downloaded PDF.
    """

    data = pd.read_csv(agreement_metadata_path)
    output_paths = []
    for index, row in tqdm.tqdm(data.iterrows()):
        url = row["agreement_url"]
        response = requests.get(url)

        output_path = f"{DATA_DIR}/raw/{url.split('/')[-1]}"
        with open(output_path, "wb") as f:
            f.write(response.content)
        output_paths.append(output_path)

    data["raw_path"] = output_paths
    data.to_csv(agreement_metadata_path, index=False)


if __name__ == "__main__":
    # extract_agreements_metadata()
    download_agreements(f"{DATA_DIR}/raw/agreement_metadata.csv")

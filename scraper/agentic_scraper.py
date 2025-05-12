from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
import asyncio
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from browser_use import Agent, Browser, BrowserConfig

load_dotenv()


# Configure the browser to connect to your Chrome instance
browser = Browser(
    config=BrowserConfig(
        # Specify the path to your Chrome executable
        browser_binary_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS path
        # For Windows, typically: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
        # For Linux, typically: '/usr/bin/google-chrome'
    )
)


async def extract_agreements(instructions, category, logs_path):

    # llm = ChatAnthropic(model="claude-3-7-sonnet")
    llm = ChatOpenAI(model="gpt-4o")
    # llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
    agent = Agent(
        task=instructions,
        llm=llm,
        browser=browser,
        use_vision=True,
        save_conversation_path=os.path.join(logs_path, category),
    )
    await agent.run()
    await browser.close()


if __name__ == "__main__":

    # base_url = "https://www.sagaftra.org/production-center"
    base_url = "https://www.sagaftra.org/production-center/contract/813/getting-started"
    categories = [
        # "Commercials",
        # "Corporate / Educational",
        # "Dubbing",
        # "Interactive",
        # "Music Videos",
        # "New Media Contracts",
        # "Sound Recordings",
        # "Television Contracts",
        # "Theatrical Contracts",
    ]
    template = """1. Go to the URL: {base_url}
    2. In the production center, go to the Category {category}
    3. If the category has multiple subcategories, iterate through each subcategory if present
    4. Go to the Agreement tab
    5. From the list of items in the Agreement tab, extact the following:
        - URL to download the PDF: there is either a hyperlink on the title of the agreement, or a hyperlink on the right side of the title of the agreement using a button with an arrow icon or download icon.
        - Category (this is the Category that you are currently scraping)
        - Subcategory (this is the Subcategory that you are currently scraping, if present)
        - Title of the agreement
        - Text: any text describing the agreement, or providing additional information on the agreement

    6. Create a json list with the following fields: Category, Subcategory, Title, Text
    7. Return the json list as a string

        """
    #         - URL to download the PDF: there is either a hyperlink on the title of the agreement, or a hyperlink on the right side of the title of the agreement using a button with an arrow icon or download icon.

    # TODO: Launch all the categories in parallel.
    for category in categories:
        logs_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/logs"
        instructions = template.format(base_url=base_url, category=category)
        asyncio.run(
            extract_agreements(instructions=instructions, category=category, logs_path=logs_path)
        )


# BUG: Instead of simply extracting the hyperlink, it tries to clikc on the PDF hyperlink, which tries to open a new tab with PDF and fails

from mistralai import Mistral
import os
import re
import sys
from openai import OpenAI
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import retry_on_error


@retry_on_error()
def get_markdown_from_pdf(file_path):

    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    uploaded_pdf = client.files.upload(
        file={
            "file_name": file_path,
            "content": open(file_path, "rb"),
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

    return markdown_text


def call_openai(system_prompt: str, prompt: str, output_schema: BaseModel):

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=16384,
        response_format=output_schema,
    )

    message = completion.choices[0].message
    if message.parsed:
        return message.parsed
    else:
        print(message.refusal)
        raise TypeError(message.refusal)


def convert_pdf_to_markdown(file_path, output_dir):
    file_name = os.path.basename(file_path)
    print(
        file_name,
        file_name.split(".pdf")[0],
        os.path.join(output_dir, file_name.split(".pdf")[0] + ".md"),
    )
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    markdown_text = get_markdown_from_pdf(file_path)
    with open(os.path.join(output_dir, file_name.split(".pdf")[0] + ".md"), "w") as f:
        f.write(markdown_text)


def chunk_markdown(markdown_text, file_path):
    # Chunk based on \n\n or based on # type of identifiers which in Markdown represent titles
    chunks = markdown_text.split("\n")
    refined_chunks = []
    for chunk in chunks:
        split_chunk = re.split(r"(?=#+\s)", chunk.strip())
        for el in split_chunk:
            if len(el) > 0:
                refined_chunks.append(el)
    return refined_chunks


def extract_identifiers(text_chunk):

    system_prompt = """You are a precise legal document structure analyzer. 

You must:
- Be extremely precise in pattern recognition
- Follow the exact output schema provided
- Return null values when appropriate
- Consider context and legal document structure conventions
- Maintain consistency in classification across similar patterns

You must not:
- Modify or normalize the original text
- Create identifiers where none exist"""

    prompt = """You are given an excerpt in markdown format from a legal text and your task is to determine if the input text contains a hierarchical level identifier. 
    Hierarchical level identifiers denote the structure of the text, indicating if the excerpt is a title, subtitle, or paragraph.

    
    1.IDENTIFIER LEVELS:
    Level 1 (Main Sections): start with markdown title characters, i.e. one or more # symbols    
    Level 2 (Major Subsections): Start with capital letters, i.e. A, B, C, etc.
    Level 3 (Numbered Items): Start with numbers in parentheses    
    Level 4 (Lowercase Letters): Start with lowercase letters in parenthesis
    Level 5 (Roman Numerals): STart with roman numerals in parenthesis
    Level 6 (Special Cases): Any other structured identifiers that don't fit the above patterns
    ###################################################################

    2. OUTPUT FORMAT
    You will return a JSON object with the following schema:
    {{
        "reasoning": string,  # your reasoning for the classification, which part of the input text made you infer that it is an identifier
        "contains_identifier": boolean,  # true if the text contains any hierarchical identifier
        "identifier_level": integer | null,  # level 1-6, or null if no identifier
        "identifier": string,  # Part of text that represents the identifier (e.g. "## 2. ", "### Title", "A.", "1.", etc.)
        "identifier_text": string | null,  # If there is a title, return the title text
        "confidence": float  # your confidence in the classification (0.0 to 1.0)
    }}
    ###################################################################

    3. RULES:
    -  Return null for identifier_level if contains_identifier is false
    -  Extract only the identifier portion, not the full content
    -  If the identifier has a title, return the title text
    -  If multiple identifiers exist, choose the most prominent one
    ###################################################################


    TEXT TO BE ANALYZED:
    {text_chunk}
    
    Answer in JSON format, related to the TEXT TO BE ANALYZED:
    """

    class Identifier(BaseModel):
        contains_identifier: bool
        identifier_level: int | None
        identifier: str
        identifier_text: str | None
        confidence: float
        reasoning: str

    return call_openai(system_prompt, prompt.format(text_chunk=text_chunk), Identifier)


def consolidate_chunks(chunks):
    # Artifact of the pdf -> markdown conversion
    # If there are two consecutive chunks with the same level of identifier, they likely belong to the same "title" and
    # we can join them together.

    # Otherwise, we propagate the latest identifier to the next chunk. Each level is propagated
    # only until a new higher level identifier is found.

    # Create the uid for the chunks here

    return


if __name__ == "__main__":

    # original_version_file_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/2014-2018_network_television_code_v13.pdf"
    amendment_file_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/changes/2018MOA-TV-National-Code_0.pdf"
    output_dir = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/markdown"

    # if not os.path.join(output_dir, "2014-2018_network_television_code_v13.md"):
    #     print("Converting PDF to markdown")
    #     convert_pdf_to_markdown(file_path=amendment_file_path, output_dir=output_dir)

    with open(
        os.path.join(output_dir, "2014-2018_network_television_code_v13.md"),
        "r",
    ) as f:
        markdown_text = f.read()

    print("Chunking markdown")
    chunked_markdown = chunk_markdown(markdown_text, file_path=amendment_file_path)

    print("Number of chunks: ", len(chunked_markdown))
    for idx in range(0, len(chunked_markdown), 400):
        print(chunked_markdown[idx])
        print(extract_identifiers(chunked_markdown[idx]))
        print("-" * 100)

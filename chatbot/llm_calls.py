from mistralai import Mistral
import os
from dotenv import load_dotenv
from google import genai

from pydantic import BaseModel
from typing import Optional


def get_markdown_from_pdf(file_path):
    mistral_client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    uploaded_pdf = mistral_client.files.upload(
        file={
            "file_name": file_path,
            "content": open(file_path, "rb"),
        },
        purpose="ocr",
    )
    signed_url = mistral_client.files.get_signed_url(file_id=uploaded_pdf.id)

    ocr_response = mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": signed_url.url,
        },
    )

    # Create single markdown string from ocr response
    markdown_text = ""
    for page in ocr_response.pages:
        markdown_text += page.markdown

    return markdown_text


# Gemini API calls and prompts


def create_initial_answer_prompt(context, question):
    prompt = """
You are a specialized assistant focused on SAG-AFTRA agreements and contracts. 
Your task is to analyze the provided context and question, then return a structured JSON response.
Provide accurate, well-referenced answers based solely on the provided context from official SAG-AFTRA documents.
Use the following schema for your response:

{{
    "relevant_text": "The exact text from the agreement that answers the question",
    "citations": {{
        "agreement_name": "Name of the agreement",
        "section": "Section number/title",
        "paragraph": "Paragraph/Item number",
        "page": "Page number (if available)"
    }},
    "answer": "Clear and concise answer to the question"
}}

Question:
{question}

Context:
{context}
"""
    return prompt.format(context=context, question=question)


class Citation(BaseModel):
    agreement_name: str
    section: str
    paragraph: Optional[str] = None
    page: Optional[int] = None


class SAGResponse(BaseModel):
    relevant_text: str
    citations: Citation
    answer: str


class RefinedResponse(BaseModel):
    amendment_relevant_text: Optional[str] = None
    refined_answer: str


def create_refine_answer_prompt(context, question, initial_relevant_context, initial_answer):
    prompt = """
You are a specialized assistant focused on SAG-AFTRA agreements and their amendments. 
Your task is to analyze if any amendments modify or affect the initial answer, and provide a structured response.

Question:
{question}

Initial agreement context:
{initial_relevant_context}

Initial Answer:
{initial_answer}

Amendment Context:
{context}

Please analyze the amendments and provide your response in the following JSON format:
{
    "amendment_relevant_text": "The exact text from amendments that modifies the initial answer (null if no relevant amendments)",
    "refined_answer": "The updated answer incorporating any amendments, or the original answer if no changes apply",
}

Important guidelines:
1. Determine if the amendments is even relevant based on the date when the amendment became valid, and the question date (if no explicit date is provided, use the current date, i.e. April 2025)
2. If no relevant amendments are found, keep the initial answer and set is_answer_changed to false
"""

    return prompt.format(
        question=question,
        initial_relevant_context=initial_relevant_context,
        initial_answer=initial_answer,
        context=context,
    )


def call_gemini_api(prompt, response_format: BaseModel):
    # Configure the API
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    # Load Gemini Pro model
    model = genai.GenerativeModel("models/gemini-2.0-flash")  # gemini-2.5-pro-preview-03-25')

    # Configure generation parameters for structured output
    generation_config = {
        "temperature": 0.0,  # Lower temperature for more precise responses
        "top_p": 0.8,
        "top_k": 40,
        "max_output_tokens": 20000,
    }
    try:
        # Generate response
        # response = model.generate_content(
        #     prompt,
        #     generation_config=generation_config,
        #     config={
        #         "response_mime_type": "application/json",
        #         "response_schema": response_format,
        #     },
        # )
        client = genai.Client(api_key="GEMINI_API_KEY")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_format,
            },
        )

        try:
            parsed_response: SAGResponse = response.parsed
            return parsed_response
        except Exception as e:
            print(f"Error parsing JSON response: {e}")
            return {"error": "Failed to parse response as JSON", "raw_response": response.text}

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return {"error": str(e), "raw_response": None}


if __name__ == "__main__":

    load_dotenv()
    original_version_file_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/2014-2018_network_television_code_v13.pdf"
    amendment_file_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/changes/2018MOA-TV-National-Code_0.pdf"

    # Preprocess the files
    original_version_file_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/2014-2018_network_television_code_v13.pdf"
    amendment_file_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/changes/2018MOA-TV-National-Code_0.pdf"

    original_version_markdown = get_markdown_from_pdf(original_version_file_path)
    amendment_markdown = get_markdown_from_pdf(amendment_file_path)

    # Create prompt
    question = (
        "What was the effective rate on October 2016 for a 40-minute single program performance?"
    )
    prompt = create_initial_answer_prompt(original_version_markdown, question)

    # Call Gemini API
    response = call_gemini_api(prompt, SAGResponse)

    print(response)

    # Refine answer
    prompt = create_refine_answer_prompt(
        context=amendment_markdown,
        question=question,
        initial_relevant_context=response.relevant_text,
        initial_answer=response.answer,
    )
    response = call_gemini_api(prompt, RefinedResponse)
    print(response)

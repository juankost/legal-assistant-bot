# SAG-AFTRA Agreement Chatbot - Work Progress

## Project Objectives

1. Business objective:
   Create a website containing a chatbot that answers questions about SAG-AFTRA agreements, providing references to the specific agreement sections used for the answer. The chatbot must handle temporal updates to the agreements correctly (i.e., use the agreement version valid for the time context of the query).

2. Learning objective:
   Try out new technologies: lovable.dev, Gemini (Google AI Studio), Qdrant, HippoRAG 2, browser-use, DocLing, Mistral OCR

## Chosen Technologies

- **Vector Store:** Qdrant (if needed, if small enough could I just keep the data in RAM?)
- **Retrieval Algorithm:** HippoRAG 2 (Graph-based retrieval with PageRank)
- **LLM w/ tool use:**: Gemini Pro, GPT-4o --> RAG is the tool that can be used to retrieve more relevant information.
- **Agent Framework:** Need to figure out what frameworks are already available --> Can I pass the Retrieval as a tool use to the LLM, and which can then reason
- **PDF Preprocessing:** Mistral OCR API / Docling + Gemini
- **Backend API:** FastAPI with Pydantic
- **Data Scraping:** `browser-use` library.
- **LLM (Generation):** Gemini Pro, GPT-4o
- **Embedding Model:** Nvidia NV Embed v2 / Cohere Embed 4
- **Frontend:** Use lovable.dev to create the interface.

## Key challenges:

Ensuring the correctness of the temporal retrieval. In many cases, a new document has an implicit
reference to the previous document, so we need to have a way to preprocess the documents to extract
these (implicit) links and add them to the Graph that is built by HippoRAG 2.

## Development Plan

**Phase 1: Basic RAG over the SAG-AFTRA agreements**

1.  **Website Scraping & Metadata Extraction:**

    - (1 day) Create a metadata.csv file with the following columns: Category, Subcategory, Title, Text, Valid From, Valid To. Save the metadata.csv file in the data/raw folder.
    - (1 day) Download the PDFs and save them in the data/raw folder. Add the path to each file to the metadata.csv file
    - (2 days) Use an LLM to infer the validity period of the agreement based on the text of the agreement.
    - (1 day) Test using browser-use library to scrape the data --> It sucks so FAR!

2.  **PDF Conversion & Chunking:**

    - (1 days) Create pipelin to convert the PDFs to Markdown using Mistral OCR and saving to new forlder, update the metadata.csv file with the processed file path.
    - (1 week) Option 1 : - Use Mistral OCR to convert the PDFs to Markdown. - Chunk the Markdown by length - Initialize a HippoRAG 2 graph with the chunks - Store the graph in a Qdrant collection
    - (1 week) Option 2 : - Explore how can I parse and chunk the files using Docling+Gemini - Target: I would like to be able to chunk based on semantically meaningful units, e.g. articles, sections, paragraphs, etc. - Initialize a HippoRAG 2 graph with the chunks - Store the graph in a Qdrant collection

3.  **Creation of the RAG chatbot:**

    - (2 days) Create API endopoint for the Retrieval with HippoRAG 2
    - (1 day) Investigate existing interfaces for chatbots, if I can leverage any of them
    - (1 week) Create the chatbot interface with lovable.dev
    - (2 days) Create a landing page with lovable.dev

4.  **Deployment:**

    - (1 day) Investigate what are the options for deployment: Google Cloud Run, Vercel, etc.
    - (2 days) Deploy the chatbot on Google Cloud Run
    - (1 day) Buy domain name and set it up on Google Cloud Run
    - (2 days) Deploy the website on Google Cloud Run

** Phase 2: Agentic RAG over the SAG-AFTRA agreements**

- investigate what are the approaches to Agentic search

** Phase 3: Agentic HippoRAG over the SAG-AFTRA agreements**

- Adapt the HippoRAG to my usecase --> custom links extraction from chunks, and how to weight the edges

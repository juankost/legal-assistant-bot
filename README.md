# Problem statement

e.g. SAG-AFTRA has multiple rules / agreements that get updatd over time, but they are never consolidated
i.e. they do not get consolidated, so it's hard to know what is the latest state of the agreement
Consequently, it takes longer to answer any questions about the agreements

This pain point is shared also in other legal professions where you have data in pdfs/word, that
has not been yet properly structured

# Solution

A legal assistant bot that can answer questions on the agreements based on the latest state of the
agreements. It would be running a HippoRAG style approach over the preprocessed data corpus, ensuring
that it only uses the latest relevant parts of the documents to answer questions.

# MVP

- Landing page
- RAG chatbot (even just using the hugging face vectara/legal-assistant agent example)
- Preprocessed once the SAG-AFTRA agreements and create the database with them
  - Preprocessing steps (how will each chunk be saved in the database):
    - chunk text
    - validity range
    - previous chunk
    - following chunk
    - theme it belongs to
    - from which document it comes from
    - Unique identifier of the chunk
    - hierarchy of the chunk (i.e. which article, section, paragraph, ...)
    - Links to other chunks:
      - explicitly linked chunks
      - links to chunks with common parent
    - Extracted legal terms (explicit or implicit) from the chunk
- Adapt the HippoRAG codebase to use my definition of the knowledge graph (i.e. the links)
  - No need to add new chunks to the knowledge graph - this I can use my preprocessing pipelien
  - Extracting relevant chunk:
    - filter to only the temporally valid data
    - from query extract the relevant legal terms --> find the chunks that contain these terms
    - additionally, also extract the cosine similarity of query to other chunks

# Target market

- Where there is a lot of legal text that is not yet structured - e.g. SAG-AFTRA

# Contact person / early adopter

It must be one of these:

Pierce Kelaita (GenAI Collective)
Mahika Popli (Cambridge)
Leo Park (System.legal)
Campbell Hutcheson
Colin Rule (AAA)
Bryan Davis (Centari)
Zeb Anderson (System.legal)
Marzieh Nabi (CodeX)
Robert Kingan (Bloomberg)
Sung Kim (Upstage)
Lucy Park (Upstage)
Mansi Shah (Kilpatrick Townsend)
Atchuth Naveen Chilaparasetti (LMNT)
Naomi Swalze (Centari)
Anil Katti (Uttara Labs)
Rongfei Lu

Target markets:
Legal texts that do not yet have the preprocessing done (i.e. linking different articles, ...)

# Installation

This project uses Conda for managing dependencies.

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd legal-assistant-bot
    ```

2.  **Create and activate Conda environment:**

    ```bash
    conda env create -f environment.yml  # Assuming you'll create an environment.yml
    conda activate legal-assistant-env # Or your chosen environment name
    ```

    Alternatively, if you prefer to manage packages manually or from `requirements.txt`:

    ```bash
    conda create -n legal-assistant-env python=3.9 # Or your desired Python version
    conda activate legal-assistant-env
    pip install -r requirements.txt
    ```

    _Note: It's recommended to create an `environment.yml` file for more reproducible Conda environments. You can create one using `conda env export > environment.yml` once your environment is set up._

3.  **Initialize and update the submodule:**

    ```bash
    git submodule init
    git submodule update
    ```

4.  **Set up any necessary API keys or configurations:**
    (Add details here if your application requires API keys, e.g., for OpenAI, or other configurations. You might use a `.env` file for this.)

# Repository Structure

The repository is organized as follows:

```
legal-assistant-bot/
├── .git/                      # Git version control files
├── .gitignore                 # Specifies intentionally untracked files that Git should ignore
├── .cursor/                   # Cursor IDE specific files
├── README.md                  # This file: Overview, setup, and usage instructions
├── requirements.txt           # Python package dependencies (for pip)
├── environment.yml            # (Recommended) Conda environment specification
├── 3rdparty/                  # Third-party libraries and submodules
│   └── HippoRAG/              # HippoRAG submodule
├── data/                      # All data files
│   ├── raw/                   # Original, unmodified data
│   ├── markdown/              # Data converted to Markdown format
│   ├── logs/                  # Log files from application runs
│   ├── mturk/                 # Data related to Amazon Mechanical Turk tasks
│   │   ├── input/             # Input files for MTurk HITs
│   │   └── output/            # Raw output/results from MTurk
│   └── processed/             # Processed or validated data ready for use
├── deprecated/                # Older files and versions no longer in active use
├── docs/                      # Documentation files
│   ├── prd/                   # Product Requirement Documents
│   │   └── mech-turk-data-validation.md # PRD for Mechanical Turk data validation
│   └── progress/              # Progress tracking documents
│       └── work-progress.md   # Document tracking overall work progress
├── notebooks/                 # Jupyter notebooks for experimentation and analysis
├── scripts/                   # Utility scripts (e.g., for deployment, data conversion)
├── src/                       # Source code for the project
│   ├── chatbot/               # Core logic for the RAG chatbot
│   ├── knowledge_graph/       # Code related to building and using the knowledge graph (e.g., HippoRAG adaptation)
│   ├── mechanical_turk/       # Modules for interacting with Mechanical Turk (e.g. API, HIT creation, results processing)
│   ├── preprocessing/         # Scripts and modules for data preprocessing
│   ├── scraper/               # Code for scraping data from various sources
│   └── utils.py               # Common utility functions and classes
└── tests/                     # Automated tests
    ├── test_chatbot/          # Tests for the chatbot module
    ├── test_preprocessing/    # Tests for the preprocessing module
    └── ...                    # Other module-specific tests
```

| Title                                                                                                            | Text                                                                                                                                                       | Valid From | Valid To |
| ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------- |
| 2022 Corporate Educational and Non-Broadcast Contract Ebook                                                      | Informational / Guide PDF                                                                                                                                  | 2022       |          |
| 12/21/22 Extension to the COVID-19 Co/Ed & Non-Broadcast Contract Production Safety & Testing Protocol Agreement |                                                                                                                                                            | 12/21/22   |          |
| Notice of Termination of Co-Ed COVID Protocols 2023                                                              |                                                                                                                                                            |            | 2023     |
| COVID-19 Production Safety and Testing Protocol Agreement for Corporate-Educational and Non-Broadcast Contracts  | Informational / Guide PDF                                                                                                                                  |            |          |
| 2022 Corporate-Educational & Non-Broadcast Print Campaign Waiver                                                 | This waiver allows a producer on a print campaign to compensate only profession performers for b-roll/behind-the-scenes footage. Informational / Guide PDF | 2022       |          |
| Corporate/Educational & Non-Broadcast Auto/Trade Show Waiver                                                     | Informational / Guide PDF                                                                                                                                  |            |          |
| 2022 Atlanta Local Corporate-Educational Code                                                                    | Informational / Guide PDF                                                                                                                                  | 2022       |          |
| 2022 Arizona-Utah Local Corporate-Educational Code                                                               | Informational / Guide PDF                                                                                                                                  | 2022       |          |
| 2022 Chicago Local Corporate-Educational Code                                                                    | Informational / Guide PDF                                                                                                                                  | 2022       |          |
| 2022 Hawaii Local Corporate-Educational Code                                                                     | Informational / Guide PDF                                                                                                                                  | 2022       |          |

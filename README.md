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

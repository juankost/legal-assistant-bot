from qdrant_client import QdrantClient, models
import tqdm
import os
import json
import re
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import openai
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import uuid

load_dotenv()


class QueryModel(BaseModel):
    query: str
    date: Optional[datetime] = None


class QueryConfig(BaseModel):
    top_k: int = 5


class QdrantDB:
    def __init__(
        self,
        collection_name: str = "sftra_agreements",
        qdrant_path: str = ":memory:",  # can be :memory:, a local path, or a URL
    ):
        self.collection_name = collection_name
        self.client = QdrantClient(path=qdrant_path)
        try:
            self.client.get_collection(collection_name=self.collection_name)
        except Exception:
            self.create_collection_with_temporal_payload()

        self.valid_from_col = "valid_from"
        self.valid_to_col = "valid_to"
        self.openai_client = openai.OpenAI()

    def load_collection(self, data_path: str):
        self.client.load_collection(
            collection_name=self.collection_name,
            path=data_path,
        )

    def create_collection_with_temporal_payload(self):
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=3072, distance=models.Distance.COSINE),
        )

        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="valid_from_timestamp",
            field_schema=models.PayloadSchemaType.INTEGER,
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="valid_to_timestamp",
            field_schema=models.PayloadSchemaType.INTEGER,
        )

    def add_document_to_collection(self, json_doc: dict):

        embedding_vector = self.embed_chunk(json_doc)
        valid_from = json_doc[self.valid_from_col]
        valid_to = json_doc[self.valid_to_col]
        valid_from_timestamp = self.convert_date_to_timestamp(valid_from)
        valid_to_timestamp = self.convert_date_to_timestamp(valid_to)

        # Generate a deterministic UUID for the document ID
        unique_name_for_id = f"{json_doc['agreement_id']}_{json_doc['chunk_index']}"
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_name_for_id))

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=doc_id,
                    vector=embedding_vector,
                    payload={
                        "chunk_text": json_doc["chunk_text"],
                        "valid_from_timestamp": valid_from_timestamp,
                        "valid_to_timestamp": valid_to_timestamp,
                        "agreement_id": json_doc["agreement_id"],
                        "chunk_index": json_doc["chunk_index"],
                        "agreement_title": json_doc["agreement_title"],
                        "agreement_url": json_doc["agreement_url"],
                        "agreement_info": json_doc["agreement_info"],
                        "category": json_doc["category"],
                        "subcategory": json_doc["subcategory"],
                        "previous_context": json_doc["previous_context"],
                        "following_context": json_doc["following_context"],
                        "valid_from": json_doc["valid_from"],
                        "valid_to": json_doc["valid_to"],
                        "impacted_agreements": json_doc["impacted_agreements"],
                    },
                )
            ],
        )

    def add_folder_to_collection(self, folder_path: str):
        for file in tqdm.tqdm(os.listdir(folder_path)):
            if file.endswith(".json"):
                with open(os.path.join(folder_path, file), "r") as f:
                    json_doc = json.load(f)
                    try:
                        self.add_document_to_collection(json_doc)
                    except Exception as e:
                        print(f"Error adding document {file}: {e}")
                        continue

    def embed_chunk(self, json_doc: dict):
        full_context = f"{json_doc['previous_context']} {json_doc['chunk_text']} {json_doc['following_context']}"  # noqa
        embedding_vector = self.embed_text(full_context)
        return embedding_vector

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(
            (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
            )
        ),
    )
    def embed_text(self, text: str):
        response = self.openai_client.embeddings.create(
            input=[text], model="text-embedding-3-large"
        )
        return response.data[0].embedding

    def convert_date_to_timestamp(self, date_str: str):
        # Expected input format: YYYY/MM/DD, raise Error if not
        if re.match(r"^\d{4}/\d{2}/\d{2}$", date_str) is None:
            raise ValueError(f"Invalid date format: {date_str}")
        return int(datetime.strptime(date_str, "%Y/%m/%d").timestamp())

    def retrieve(self, query: QueryModel, config: QueryConfig):

        if query.date is not None:
            query_date_timestamp = self.convert_date_to_timestamp(query.date)
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="valid_from_timestamp", range=models.Range(lte=query_date_timestamp)
                    ),
                    models.FieldCondition(
                        key="valid_to_timestamp", range=models.Range(gte=query_date_timestamp)
                    ),
                ]
            )
        else:
            query_filter = None

        start_time = time.time()
        query_vector = self.embed_text(query.query)
        end_time = time.time()
        print(f"Time taken to embed text: {end_time - start_time} seconds")

        start_time = time.time()
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=config.top_k,
            with_payload=True,
        )
        end_time = time.time()
        print(f"Time taken to search: {end_time - start_time} seconds")
        return search_result


if __name__ == "__main__":

    # Test the QdranDB class on my local machine using the chunked data
    chunks_dir = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/chunks"
    qdrant_path = "/Users/juankostelec/Google_drive/Projects/legal-assistant-bot/data/qdrant_db"
    qdrant_db = QdrantDB(qdrant_path=qdrant_path)
    # qdrant_db.add_folder_to_collection(chunks_dir)

    # Test retrieving a document
    query = QueryModel(
        query="What is the validity of the agreement for the Commercials?", date=None
    )
    config = QueryConfig(top_k=1)
    import time

    result = qdrant_db.retrieve(query, config)
    print(result)

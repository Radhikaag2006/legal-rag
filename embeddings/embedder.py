import json
import os

import pandas as pd

from embeddings.embedding_model import EmbeddingModel
from embeddings.chroma_store import ChromaStore

from preprocessing.config import (
    CSV_PATH,
)

from preprocessing.checkpoint import (
    initialize_checkpoint,
    initialize_document,
    is_stage_complete,
    mark_stage_complete
)


def embed_documents():

    print("=" * 70)
    print("GENERATING EMBEDDINGS")
    print("=" * 70)

    initialize_checkpoint()

    df = pd.read_csv(CSV_PATH)

    embedding_model = EmbeddingModel()

    vector_db = ChromaStore()

    total_documents = len(df)

    for index, row in df.iterrows():

        print(f"\n[{index + 1}/{total_documents}]")

        document_id = str(row["document_id"])

        initialize_document(document_id)

        if is_stage_complete(document_id, "embed"):
            print(f"Skipping : {document_id}")
            continue

        chunk_json_path = row["chunk_json_path"]

        if not os.path.exists(chunk_json_path):
            print(f"Chunk file not found : {chunk_json_path}")
            continue

        print(f"Processing : {document_id}")

        with open(chunk_json_path, "r", encoding="utf-8") as file:
            chunks = json.load(file)

        texts = []
        ids = []
        metadatas = []

        for chunk in chunks:

            texts.append(chunk["text"])

            ids.append(f'{chunk["document_id"]}_{chunk["chunk_id"]}')

            metadatas.append(
                {
                    "document_id": chunk["document_id"],
                    "chunk_id": chunk["chunk_id"],
                    "case_title": chunk["case_title"],
                    "court": chunk["court"],
                    "date": chunk["date"],
                }
            )

        embeddings = embedding_model.embed_texts(texts)

        vector_db.add_documents(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        mark_stage_complete(document_id, "embed")

        print(f"Embedded {len(texts)} chunks.")

    print("\n" + "=" * 70)
    print("Embedding Completed Successfully.")
    print(f"Total Vectors Stored : {vector_db.count()}")
    print("=" * 70)


if __name__ == "__main__":
    embed_documents()
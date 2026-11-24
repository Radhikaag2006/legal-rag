import chromadb

from preprocessing.config import (
    VECTOR_DB_PATH,
    COLLECTION_NAME
)


class ChromaStore:

    def __init__(self):

        print("Initializing ChromaDB...")

        self.client = chromadb.PersistentClient(
            path=VECTOR_DB_PATH
        )

        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME
        )

        print("ChromaDB initialized successfully.\n")

    # ---------------------------------------------------------
    # Add a single document
    # ---------------------------------------------------------

    def add_document(
        self,
        document_id: str,
        embedding,
        text: str,
        metadata: dict
    ):

        self.collection.add(
            ids=[document_id],
            embeddings=[list(embedding)],
            documents=[text],
            metadatas=[metadata]
        )

    # ---------------------------------------------------------
    # Add multiple documents
    # ---------------------------------------------------------

    def add_documents(
        self,
        ids: list[str],
        embeddings,
        documents: list[str],
        metadatas: list[dict]
    ):

        embeddings = [list(embedding) for embedding in embeddings]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    # ---------------------------------------------------------
    # Query
    # ---------------------------------------------------------

    def query(
        self,
        embedding,
        top_k: int = 5
    ):

        return self.collection.query(
            query_embeddings=[list(embedding)],
            n_results=top_k
        )

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------

    def count(self):

        return self.collection.count()

    def delete_collection(self):

        self.client.delete_collection(
            COLLECTION_NAME
        )
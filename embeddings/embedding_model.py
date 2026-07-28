from sentence_transformers import SentenceTransformer

class EmbeddingModel:
    """
    Wrapper around the SEntence Transformers embedding model."""

    def __init__(self, model_name : str = "BAAI/bge-small-en-v1.5"):
        print(f"Loading embedding model: {model_name}")

        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str):
        """Generate embedding for a single text."""
        return self.model.encode(text, normalize_embeddings = True)


    def  embed_texts(self,texts:list[str]):
        """Generate embediings for multiple texts.""" 

        return self.model.encode(texts, normalize_embeddings = True) 

# TESTING 
if __name__ == "__main__":

    model = EmbeddingModel()
    sample_text = """ 
    Article 21 guarantees the Right to Life and Personal Proprty."""
    embedding = model.embed_text(sample_text)

    print(f"Embedding Dimension : {len(embedding)}")
    print()

    print("First 10 Values:")
    print(embedding[:10])   
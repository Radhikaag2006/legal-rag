import google.generativeai as genai

from preprocessing.config import GEMINI_API_KEY

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIM = 768


class EmbeddingModel:
    """Wrapper around Google's hosted embedding API (no local model weights)."""

    def __init__(self, model_name: str = EMBED_MODEL):
        self.model_name = model_name
        genai.configure(api_key=GEMINI_API_KEY)

    def embed_text(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        result = genai.embed_content(
            model=self.model_name,
            content=text,
            output_dimensionality=EMBED_DIM,
        )
        return result["embedding"]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        result = genai.embed_content(
            model=self.model_name,
            content=texts,
            output_dimensionality=EMBED_DIM,
        )
        return result["embedding"]


# TESTING
if __name__ == "__main__":

    model = EmbeddingModel()
    sample_text = """
    Article 21 guarantees the Right to Life and Personal Property."""
    embedding = model.embed_text(sample_text)

    print(f"Embedding Dimension : {len(embedding)}")
    print()

    print("First 10 Values:")
    print(embedding[:10])

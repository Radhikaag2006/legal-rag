import google.generativeai as genai

from preprocessing.config import GEMINI_API_KEY
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


class GeminiClient:

    def __init__(self):

        logger.info("Initializing Gemini...")

        genai.configure(api_key=GEMINI_API_KEY)

        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash"
        )

        print("Gemini Ready.\n")

    def generate(self, prompt: str) -> str:

        response = self.model.generate_content(prompt)

        return response.text
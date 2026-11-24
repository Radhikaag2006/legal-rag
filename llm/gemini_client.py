import google.generativeai as genai

from preprocessing.config import GEMINI_API_KEY
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


class GeminiClient:

    def __init__(self):

        logger.info("Initializing Gemini...")

        genai.configure(api_key=GEMINI_API_KEY)

        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash"
        )

        print("Gemini Ready.\n")

    def generate(self, prompt: str, temperature=None, timeout=None) -> str:

        try:
            # Fail fast instead of silently retrying for minutes when offline
            kwargs = {}
            if temperature is not None:
                kwargs["generation_config"] = genai.GenerationConfig(
                    temperature=temperature
                )
            response = self.model.generate_content(
                prompt,
                request_options={
                    "timeout": timeout or REQUEST_TIMEOUT_SECONDS,
                    "retry": None,
                },
                **kwargs,
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini request failed: {e}")
            raise RuntimeError(
                "Could not reach the Gemini language model. Check your internet "
                "connection and API key, then try again."
            ) from e
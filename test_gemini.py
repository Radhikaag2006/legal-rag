from llm.gemini_client import GeminiClient

gemini = GeminiClient()

response = gemini.generate(
    "Explain Article 14 of the Indian Constitution in simple words."
)

print("\nResponse:\n")
print(response)
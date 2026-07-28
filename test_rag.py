from rag.rag_pipeline import RAGPipeline

rag = RAGPipeline()

response = rag.ask(
    "What is Article 14 of the Constitution?"
)

print("\n")
print("=" * 80)
print("QUESTION")
print("=" * 80)
print(response["question"])

print("\n")
print("=" * 80)
print("ANSWER")
print("=" * 80)
print(response["answer"])

print("\n")
print("=" * 80)
print("SOURCES")
print("=" * 80)

for source in response["sources"]:

    print(f"Case  : {source['case_title']}")
    print(f"Court : {source['court']}")
    print(f"Date  : {source['date']}")
    print("-" * 80)
from retriever.retriever import Retriever

retriever = Retriever()

query = "What is Article 14 of the Constitution?"

results = retriever.retrieve(query, top_k=5)

for i, chunk in enumerate(results, 1):
    print("=" * 80)
    print(f"Result {i}")
    print("Case:", chunk["case_title"])
    print("Court:", chunk["court"])
    print("Date:", chunk["date"])
    print("Distance:", chunk["distance"])
    print()
    print(chunk["text"][:500])
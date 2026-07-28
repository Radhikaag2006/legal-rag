from retriever.retriever import Retriever


def main():

    retriever = Retriever()

    while True:

        query = input("\nAsk your legal question (type 'exit' to quit): ")

        if query.lower() == "exit":
            break

        results = retriever.retrieve(
            query=query,
            top_k=5
        )

        print("\n" + "=" * 80)
        print("TOP RETRIEVED CHUNKS")
        print("=" * 80)

        for index, chunk in enumerate(results, start=1):

            print(f"\nResult #{index}")

            print(f"Case Title : {chunk['case_title']}")
            print(f"Court      : {chunk['court']}")
            print(f"Date       : {chunk['date']}")
            print(f"Distance   : {chunk['distance']:.4f}")

            print("\nText:\n")

            print(chunk["text"][:600])

            print("\n" + "-" * 80)


if __name__ == "__main__":
    main()
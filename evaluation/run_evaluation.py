import json
import csv
import time
from pathlib import Path


import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import your RAG pipeline
from rag.rag_pipeline import RAGPipeline

# Gemini free tier allows 5 requests/minute for gemini-2.5-flash
REQUEST_DELAY_SECONDS = 13


def main():

    rag = RAGPipeline()

    evaluation_dir = Path(__file__).parent

    questions_file = evaluation_dir / "questions.json"
    output_file = evaluation_dir / "evaluation_results.csv"

    # Load questions
    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:

        writer = csv.writer(csvfile)

        writer.writerow([
            "ID",
            "Category",
            "Question",
            "Answer",
            "Retrieved Cases",
            "Number of Sources",
            "Response Time (sec)"
        ])

        print("=" * 100)
        print("Running RAG Evaluation...")
        print("=" * 100)

        for index, item in enumerate(questions):

            question = item["question"]

            print(f"\nQuestion {item['id']}: {question}")

            start_time = time.time()

            try:
                response = rag.ask(question)

                end_time = time.time()

                response_time = round(end_time - start_time, 2)

                answer = response.get("answer", "")

                sources = response.get("sources", [])

                retrieved_cases = ", ".join(
                    source.get("case_title", "Unknown")
                    for source in sources
                )

                writer.writerow([
                    item["id"],
                    item["category"],
                    question,
                    answer,
                    retrieved_cases,
                    len(sources),
                    response_time
                ])

                print(f"[OK] Completed ({response_time} sec)")

            except Exception as e:

                writer.writerow([
                    item["id"],
                    item["category"],
                    question,
                    f"ERROR: {str(e)}",
                    "",
                    0,
                    0
                ])

                print(f"[FAILED] {e}")

            if index < len(questions) - 1:
                time.sleep(REQUEST_DELAY_SECONDS)

    print("\n")
    print("=" * 100)
    print("Evaluation Finished!")
    print(f"Results saved to: {output_file}")
    print("=" * 100)


if __name__ == "__main__":
    main()
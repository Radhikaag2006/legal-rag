import json
import sys
from pathlib import Path

# ----------------------------------------------------
# Add project root to Python path
# ----------------------------------------------------

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ----------------------------------------------------
# Import your Retriever
# ----------------------------------------------------

from retriever.retriever import Retriever

# ----------------------------------------------------
# Load Questions
# ----------------------------------------------------

QUESTIONS_FILE = project_root / "evaluation" / "questions.json"

with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
    questions = json.load(f)

retriever = Retriever()

# ----------------------------------------------------
# Label Questions
# ----------------------------------------------------

for question in questions:

    # Skip already labelled questions
    if question["relevant_doc_ids"]:
        continue

    print("\n" + "=" * 80)
    print(f"Question {question['id']}")
    print("=" * 80)

    print(question["question"])
    print()

    retrieved = retriever.retrieve(
        query=question["question"],
        top_k=10
    )

    if len(retrieved) == 0:
        print("No documents retrieved.")
        continue

    print("Retrieved Documents:\n")

    for idx, chunk in enumerate(retrieved, start=1):

        print(f"[{idx}]")

        print(f"Case Title  : {chunk['case_title']}")
        print(f"Document ID : {chunk['document_id']}")
        print(f"Court       : {chunk['court']}")
        print(f"Date        : {chunk['date']}")

        preview = chunk["text"][:250].replace("\n", " ")

        print(f"Preview     : {preview}...")

        print("-" * 80)

    print()
    print("Enter the correct document numbers separated by commas.")
    print("Example: 1,3,5")
    print("Press ENTER if none are correct.\n")

    user_input = input("Selection: ").strip()

    selected_doc_ids = []

    if user_input != "":

        try:

            indices = [
                int(x.strip())
                for x in user_input.split(",")
            ]

            for idx in indices:

                if 1 <= idx <= len(retrieved):

                    selected_doc_ids.append(
                        retrieved[idx - 1]["document_id"]
                    )

        except Exception:

            print("Invalid input. Skipping...")

    question["relevant_doc_ids"] = selected_doc_ids

    # Save after every question
    with open(
        QUESTIONS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            questions,
            f,
            indent=4,
            ensure_ascii=False
        )

print("\nGround Truth Labeling Complete!")
import os
import fitz
import pandas as pd

from preprocessing.config import (
    CSV_PATH,
    TEXT_FOLDER
)

from preprocessing.checkpoint import (
    initialize_checkpoint,
    initialize_document,
    is_stage_complete,
    mark_stage_complete
)


# =====================================================
# Extract Text From PDF
# =====================================================

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract complete text from a PDF.
    """

    document = fitz.open(pdf_path)

    pages = []

    for page in document:
        pages.append(page.get_text())

    document.close()

    return "\n".join(pages)


# =====================================================
# Save Text
# =====================================================

def save_text(text: str, output_path: str):
    """
    Save extracted text into a TXT file.
    """

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)


# =====================================================
# Process One PDF
# =====================================================

def process_single_pdf(row):
    """
    Extract text from one PDF.
    """

    document_id = str(row["document_id"])

    initialize_document(document_id)

    pdf_path = row["pdf_path"]

    text_path = os.path.join(
        TEXT_FOLDER,
        f"{document_id}.txt"
    )

    # -------------------------------------------------
    # Skip already processed PDFs
    # -------------------------------------------------

    if (
        is_stage_complete(document_id, "extract_text")
        and os.path.exists(text_path)
    ):

        print(f"Skipping : {document_id}")

        row["text_path"] = text_path

        return row, "skipped"

    # -------------------------------------------------
    # Extract Text
    # -------------------------------------------------

    try:

        print(f"\nProcessing : {document_id}")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(
                f"PDF not found : {pdf_path}"
            )

        text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            raise Exception(
                "No extractable text found."
            )

        save_text(text, text_path)

        mark_stage_complete(
            document_id,
            "extract_text"
        )

        row["text_path"] = text_path

        print(f"Saved : {text_path}")

        return row, "success"

    except Exception as error:

        print(f"Failed : {document_id}")

        print(error)

        row["text_path"] = ""

        return row, "failed"


# =====================================================
# Process All PDFs
# =====================================================

def process_all_pdfs():

    initialize_checkpoint()

    dataframe = pd.read_csv(CSV_PATH)

    # -------------------------------------------------
    # Add column if missing
    # -------------------------------------------------

    if "text_path" not in dataframe.columns:

        dataframe["text_path"] = ""

    total = len(dataframe)

    success = 0
    skipped = 0
    failed = 0

    print("=" * 70)
    print("TEXT EXTRACTION")
    print("=" * 70)
    print(f"Total PDFs : {total}")

    for index in range(total):

        print("\n" + "-" * 70)
        print(f"[{index + 1}/{total}]")

        row = dataframe.iloc[index].copy()

        updated_row, status = process_single_pdf(row)

        dataframe.iloc[index] = updated_row

        # Save progress immediately
        if status == "success":

            dataframe.to_csv(
                CSV_PATH,
                index=False
            )

            success += 1

        elif status == "skipped":

            skipped += 1

        else:

            failed += 1

    # Final save
    dataframe.to_csv(
        CSV_PATH,
        index=False
    )

    print("\n" + "=" * 70)
    print("TEXT EXTRACTION SUMMARY")
    print("=" * 70)

    print(f"Total PDFs : {total}")
    print(f"Extracted : {success}")
    print(f"Skipped    : {skipped}")
    print(f"Failed     : {failed}")

    print(f"\nUpdated CSV : {CSV_PATH}")

    print("=" * 70)


# =====================================================
# Main
# =====================================================

if __name__ == "__main__":

    process_all_pdfs()
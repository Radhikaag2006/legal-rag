import os
import pandas as pd

from preprocessing.config import (
    CSV_PATH,
    TEXT_FOLDER,
    CLEAN_TEXT_FOLDER
)

from preprocessing.checkpoint import (
    initialize_checkpoint,
    initialize_document,
    is_stage_complete,
    mark_stage_complete
)

from cleaning.headers import remove_headers_and_footers
from cleaning.unicode_clean import normalize_unicode
from cleaning.whitespace import normalize_whitespace


# =====================================================
# Read Text
# =====================================================

def read_text(text_path: str) -> str:
    """
    Read extracted text file.
    """

    with open(text_path, "r", encoding="utf-8") as file:
        return file.read()


# =====================================================
# Save Clean Text
# =====================================================

def save_clean_text(text: str, output_path: str):
    """
    Save cleaned text.
    """

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)


# =====================================================
# Cleaning Pipeline
# =====================================================

def clean_text(text: str) -> str:
    """
    Apply all cleaning operations.
    """

    text = normalize_unicode(text)

    text = remove_headers_and_footers(text)

    text = normalize_whitespace(text)

    return text


# =====================================================
# Process One Document
# =====================================================

def process_single_document(row):

    document_id = str(row["document_id"])

    initialize_document(document_id)

    text_path = row["text_path"]

    clean_text_path = os.path.join(
        CLEAN_TEXT_FOLDER,
        f"{document_id}.txt"
    )

    # -------------------------------------------------

    if (
        is_stage_complete(document_id, "clean_text")
        and os.path.exists(clean_text_path)
    ):

        print(f"Skipping : {document_id}")

        row["clean_text_path"] = clean_text_path

        return row, "skipped"

    # -------------------------------------------------

    try:

        print(f"\nProcessing : {document_id}")

        if not os.path.exists(text_path):
            raise FileNotFoundError(
                f"Text file not found : {text_path}"
            )

        text = read_text(text_path)

        cleaned_text = clean_text(text)

        if not cleaned_text.strip():
            raise Exception(
                "Cleaning produced empty text."
            )

        save_clean_text(
            cleaned_text,
            clean_text_path
        )

        mark_stage_complete(
            document_id,
            "clean_text"
        )

        row["clean_text_path"] = clean_text_path

        print(f"Saved : {clean_text_path}")

        return row, "success"

    except Exception as error:

        print(f"Failed : {document_id}")

        print(error)

        row["clean_text_path"] = ""

        return row, "failed"


# =====================================================
# Process All Documents
# =====================================================

def process_all_documents():

    initialize_checkpoint()

    dataframe = pd.read_csv(CSV_PATH)

    if "clean_text_path" not in dataframe.columns:

        dataframe["clean_text_path"] = ""

    total = len(dataframe)

    success = 0
    skipped = 0
    failed = 0

    print("=" * 70)
    print("TEXT CLEANING")
    print("=" * 70)
    print(f"Total Documents : {total}")

    for index in range(total):

        print("\n" + "-" * 70)
        print(f"[{index + 1}/{total}]")

        row = dataframe.iloc[index].copy()

        updated_row, status = process_single_document(row)

        dataframe.iloc[index] = updated_row

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

    dataframe.to_csv(
        CSV_PATH,
        index=False
    )

    print("\n" + "=" * 70)
    print("TEXT CLEANING SUMMARY")
    print("=" * 70)

    print(f"Total Documents : {total}")
    print(f"Cleaned   : {success}")
    print(f"Skipped   : {skipped}")
    print(f"Failed    : {failed}")

    print(f"\nUpdated CSV : {CSV_PATH}")

    print("=" * 70)


# =====================================================
# Main
# =====================================================

if __name__ == "__main__":

    process_all_documents()


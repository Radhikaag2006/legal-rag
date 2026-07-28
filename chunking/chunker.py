import json 
import os 

import pandas as pd

from preprocessing.config import(CSV_PATH, CHUNK_FOLDER)

from preprocessing.checkpoint import (initialize_checkpoint, initialize_document, is_stage_complete, mark_stage_complete)

from chunking.splitter import split_text

def read_clean_text(path : str):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()
    
def save_chunks(chunks,output_path):

    with open(output_path,"w",encoding="utf-8")as file:
        json.dump(chunks, file, indent=4, ensure_ascii=False)

def process_document(row):
    document_id = str(row["document_id"])

    initialize_document(document_id)

    clean_text_path = row["clean_text_path"]
    output_path = os.path.join(CHUNK_FOLDER, f"{document_id}.json")

    if (
        is_stage_complete(document_id, "chunk_text")
        and os.path.exists(output_path)
    ):
        print(f"Skipping : {document_id}")
        row["chunk_json_path"] = output_path
        return row, "skipped"

    try:
        print(f"\nProcessing : {document_id}")

        text = read_clean_text(clean_text_path)

        split_chunks = split_text(text)

        chunk_data = []
        chunk_id = 0

        for chunk in split_chunks:

            chunk = chunk.strip()

            # Skip empty chunks
            if not chunk:
                continue

            # Skip chunks with too few words
            if len(chunk.split()) < 15:
                continue

            # Skip chunks that are only numbers
            if chunk.isdigit():
                continue

           
            chunk_data.append(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "case_title": row.get("case_name", ""),
                "court": row.get("court", ""),
                "date": row.get("judgement_date", ""),
                "text": chunk,
            }
           )

            chunk_id += 1

        save_chunks(chunk_data, output_path)

        row["chunk_json_path"] = output_path
        row["chunk_count"] = len(chunk_data)

        mark_stage_complete(document_id, "chunk_text")

        print(f"Chunks : {len(chunk_data)}")

        return row, "success"

    except Exception as e:

        print(e)

        row["chunk_json_path"] = ""
        row["chunk_count"] = 0

        return row, "failed"

def process_all_documents():

    initialize_checkpoint()
    df = pd.read_csv(CSV_PATH)

    if"chunk_json_path" not in df.columns:
        df["chunk_json_path"]= ""

    if "chunk_count" not in df.columns:
        df["chunk_count"] = 0

    total = len(df)
    success = 0
    skipped = 0
    failed =0
    print("="*70)
    print("CHUNKING DOCUMENTS")
    print("="*70)

    for index in range(total):
        print(f"\n[{index+1}/{total}]")
        row = df.iloc[index].copy()
        updated_row,status = process_document(row)
        df.iloc[index] = updated_row

        if status == "success":

            success += 1
            df.to_csv(CSV_PATH, index = False)
        elif status == "skipped":

            skipped += 1
        else:

            failed += 1
    df.to_csv(CSV_PATH, index=False)

    print("\n")

    print("=" * 70)

    print("SUMMARY")

    print("=" * 70)

    print(f"Success : {success}")

    print(f"Skipped : {skipped}")

    print(f"Failed  : {failed}")

    print("=" * 70)


if __name__ == "__main__":

    process_all_documents()


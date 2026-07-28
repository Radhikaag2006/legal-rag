import json
import os

from preprocessing.config import CHECKPOINT_FILE


# =====================================================
# Configuration
# =====================================================




# =====================================================
# Initialize Checkpoint File
# =====================================================

def initialize_checkpoint():
    """
    Create the checkpoint file if it doesn't exist.
    """

    if not os.path.exists(CHECKPOINT_FILE):

        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as file:

            json.dump({}, file, indent=4)


# =====================================================
# Load Checkpoint
# =====================================================

def load_checkpoint():
    """
    Load the checkpoint JSON.
    """

    initialize_checkpoint()

    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as file:

        return json.load(file)


# =====================================================
# Save Checkpoint
# =====================================================

def save_checkpoint(checkpoint):
    """
    Save the checkpoint JSON.
    """

    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as file:

        json.dump(
            checkpoint,
            file,
            indent=4
        )


# =====================================================
# Initialize One Document
# =====================================================

def initialize_document(document_id):
    """
    Create an entry for a document if it does not exist.
    """

    checkpoint = load_checkpoint()

    if document_id not in checkpoint:

        checkpoint[document_id] = {
            "stages": {}
        }

        save_checkpoint(checkpoint)


# =====================================================
# Mark Stage Complete
# =====================================================

def mark_stage_complete(document_id, stage_name):
    """
    Mark a processing stage as completed.
    """

    initialize_document(document_id)

    checkpoint = load_checkpoint()

    checkpoint[document_id]["stages"][stage_name] = True

    save_checkpoint(checkpoint)


# =====================================================
# Check Stage Completion
# =====================================================

def is_stage_complete(document_id, stage_name):
    """
    Check whether a stage has already been completed.
    """

    initialize_document(document_id)

    checkpoint = load_checkpoint()

    return checkpoint[document_id]["stages"].get(stage_name, False)


# =====================================================
# Reset One Stage
# =====================================================

def reset_stage(document_id, stage_name):
    """
    Reset a particular stage.
    """

    initialize_document(document_id)

    checkpoint = load_checkpoint()

    checkpoint[document_id]["stages"][stage_name] = False

    save_checkpoint(checkpoint)


# =====================================================
# Reset Entire Document
# =====================================================

def reset_document(document_id):
    """
    Remove one document completely from the checkpoint.
    """

    checkpoint = load_checkpoint()

    if document_id in checkpoint:

        del checkpoint[document_id]

        save_checkpoint(checkpoint)


# =====================================================
# Get Stage Status
# =====================================================

def get_document_status(document_id):
    """
    Return the stage dictionary for a document.
    """

    initialize_document(document_id)

    checkpoint = load_checkpoint()

    return checkpoint[document_id]["stages"]


# =====================================================
# Count Completed Documents
# =====================================================

def count_completed(stage_name):
    """
    Count how many documents have completed a stage.
    """

    checkpoint = load_checkpoint()

    count = 0

    for document in checkpoint.values():

        if document["stages"].get(stage_name, False):

            count += 1

    return count


# =====================================================
# Print Summary
# =====================================================

def print_summary():
    """
    Print a summary of all processed documents.
    """

    checkpoint = load_checkpoint()

    print("\n" + "=" * 60)
    print("PREPROCESSING CHECKPOINT SUMMARY")
    print("=" * 60)

    print(f"Documents tracked : {len(checkpoint)}")

    stages = [
        "extract_text",
        "clean_text",
        "chunk_text",
        "embed"
    ]

    for stage in stages:

        print(f"{stage:<20}: {count_completed(stage)}")

    print("=" * 60)
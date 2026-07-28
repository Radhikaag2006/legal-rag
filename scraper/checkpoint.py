import json
import os

CHECKPOINT_FILE = "data/checkpoint.json"

# create checkpoint file if it does not exists 
def initialize_checkpoint():

    """ creates checkpoint file if it does not exists."""
    os.makedirs("data",exist_ok =  True)
    if not os.path.exists(CHECKPOINT_FILE):

        with open(CHECKPOINT_FILE, "w") as file:
            json.dump({}, file, indent=4)

def sync_existing_pdfs():
    """ Synchronises the checkpoints with the PDF's that already exists in data/pdf."""
    initialize_checkpoint()

    checkpoint = load_checkpoint()

    pdf_directory = "data/pdfs"
    if not os.path.exists(pdf_directory):
        return

    for file_name in os.listdir(pdf_directory):

        if  not file_name.endswith(".pdf"):
            continue

        document_id = file_name.replace(".pdf","")

        if document_id not in checkpoint:
            checkpoint[document_id] = {
                "pdf_downloaded":True,
                "parsed":False
            }

    save_checkpoint(checkpoint)
#LOAD THE CHECKPOINT 

def load_checkpoint():
    """Loads the checkpoint dictionary."""

    initialize_checkpoint()

    with open(CHECKPOINT_FILE, "r") as file :
        checkpoint = json.load(file)
    
    return checkpoint 

def save_checkpoint(checkpoint):
    """Saves the checkpoint dictiionary."""

    with open(CHECKPOINT_FILE, "w") as file:
        json.dump(checkpoint,file, indent=4)


#MARK THE PDF DOWNLOAD 
def mark_pdf_download(document_id):
    """Marks a judgement as having it's PDF downloaded."""

    checkpoint = load_checkpoint()

    if document_id not in checkpoint :
        checkpoint[document_id] = {
            "pdf_downloaded": False,
            "parsed": False
        }

    checkpoint[document_id]["pdf_downloaded"]= True
    save_checkpoint(checkpoint)


# MARk PARSED
def mark_parsed(document_id):
    """Marksjudgement as parsed."""

    checkpoint = load_checkpoint()


    if document_id not in checkpoint:

        checkpoint[document_id] = {
            "pdf_donloaded" : False,
            "parsed" : False
        }

    checkpoint[document_id]["parsed"] = True
    save_checkpoint(checkpoint)

# CHECK STATUS

def is_pdf_downloaded(document_id):
    """Returns true if the pdf has allready been downloaded."""

    checkpoint = load_checkpoint()

    return checkpoint.get(document_id,{}).get("pdf_downloaded",False)

def is_parsed(document_id):
    """Returns TRue if the judgement has already been parsed."""

    checkpoint = load_checkpoint()

    return checkpoint.get(document_id, {}).get("parsed", False)

#COMPLETED JUDGEMENT FUNCTION 
def filter_completed_judgements(metadata_list):
    """Removes judgementthat have already been processed .
    1) PDF HAS BEEN DOWNLOADED 
    2) METADATA HAS BEEN PARSED."""

    checkpoint = load_checkpoint()

    remaining = []

    skipped = 0

    for metadata in metadata_list:
        document_id = metadata["document_id"]

        if document_id in checkpoint:

            if(checkpoint[document_id]["pdf_downloaded"] and checkpoint[document_id]["parsed"]):

                skipped +=1
                print(f"Skipping complete judgement : {document_id}")
                continue
        
        remaining.append(metadata)

    print(f"\nSkipped {skipped} completed judgments.")
    print(f"Remaining judgments : {len(remaining)}")

    return remaining





     

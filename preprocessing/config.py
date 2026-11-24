import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")

#CSV 
CSV_PATH = "data/csv/judgements.csv"

# DATA FOLDERS 
PDF_FOLDER = "data/pdfs"
TEXT_FOLDER = "data/text"
CLEAN_TEXT_FOLDER = "data/clean_text"
CHUNK_FOLDER = "data/chunks"

#Chunking Configurations 

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
CHUNK_FOLDER = "data/chunks"

#vector db 
VECTOR_DB_PATH = "data/vector_db"

COLLECTION_NAME = "legal_judgements"

BATCH_SIZE = 100

#Create Directories (only relevant to the local/offline data-prep scripts;
# the request-time path on a read-only filesystem like Vercel never needs
# these, so a failure here is harmless there)

try:
    os.makedirs(TEXT_FOLDER, exist_ok=True)
    os.makedirs(CLEAN_TEXT_FOLDER, exist_ok=True)
    os.makedirs(CHUNK_FOLDER, exist_ok=True)
except OSError:
    pass

CHECKPOINT_FILE = "data/preprocessing_checkpoint.json"
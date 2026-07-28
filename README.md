# Indian Legal Assistant (Legal RAG)

A Retrieval-Augmented Generation (RAG) system for querying Indian court judgments in natural language. It scrapes judgments from [Indian Kanoon](https://indiankanoon.org), cleans and chunks them, embeds them into a local vector database, and answers questions using Google Gemini grounded strictly in the retrieved case law.

## How it works

```
Scrape (Indian Kanoon) → Extract PDF text → Clean text → Chunk text
    → Embed chunks → Store in ChromaDB → Retrieve top-k chunks → Gemini answers with citations
```

1. **Scraper** (`scraper/`, `main.py`) — searches Indian Kanoon for judgments across categories (Criminal, Civil, Constitutional, Tax, Corporate), downloads the PDFs, and parses case metadata (title, court, date) into a CSV.
2. **Preprocessing** (`preprocessing/extract_text.py`) — extracts raw text from each PDF using PyMuPDF.
3. **Cleaning** (`cleaning/`) — normalizes unicode, strips repeated headers/footers, and collapses whitespace.
4. **Chunking** (`chunking/`) — splits cleaned text into overlapping chunks (~1000 chars, 200 overlap) via LangChain's `RecursiveCharacterTextSplitter`, dropping trivial/near-empty chunks.
5. **Embeddings** (`embeddings/`) — embeds chunks with `BAAI/bge-small-en-v1.5` (Sentence Transformers) and stores them in a persistent **ChromaDB** collection.
6. **RAG pipeline** (`rag/rag_pipeline.py`) — embeds the user's question, retrieves the top-k most relevant chunks, builds a grounded prompt, and calls **Gemini 2.5 Flash** to answer using *only* the retrieved context, citing case title/court/date.
7. **Frontend** (`frontend/app.py`) — a Streamlit UI to ask questions and view the answer plus source cases.

Every stage is checkpointed (`data/checkpoint.json`, `data/preprocessing_checkpoint.json`) so scripts can be safely re-run and will skip already-completed documents/stages.

## Project structure

```
constants.py            Scraper constants (base URL, headers, search categories)
main.py                 Entry point for the scraping pipeline
scraper/                Search, download, parse Indian Kanoon judgments
preprocessing/          Config, checkpointing, PDF text extraction
cleaning/                Unicode/header/whitespace cleaning
chunking/                Text splitting into chunks
embeddings/              Embedding model + ChromaDB wrapper
retriever/               Query embedding + vector search
llm/                     Gemini client
rag/                     RAG pipeline (retrieve + prompt + generate)
frontend/                Streamlit UI
evaluation/              Batch evaluation of the RAG pipeline against sample questions
data/                    CSV, PDFs, extracted/cleaned text, chunks, checkpoints, vector DB
```

## Prerequisites

- Python 3.11+ (project venv is on 3.13)
- A [Google Gemini API key](https://aistudio.google.com/apikey)

## Setup

1. **Clone and create a virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables** — create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

## Running the project

### Option A — Use the included sample data (fastest)

The repo already ships with scraped/processed data under `data/` (CSVs, cleaned text, chunks, and checkpoints). If `data/vector_db/` already contains embeddings, you can skip straight to step 5.

### Option B — Run the full pipeline from scratch

Run each stage in order from the project root:

```bash
# 1. Scrape judgments (search → download PDFs → parse metadata → CSV)
python main.py

# 2. Extract text from downloaded PDFs
python -m preprocessing.extract_text

# 3. Clean extracted text
python -m cleaning.cleaner

# 4. Split cleaned text into chunks
python -m chunking.chunker

# 5. Generate embeddings and store them in ChromaDB
python -m embeddings.embedder
```

Each stage reads/writes `data/csv/judgements.csv` and updates the checkpoint files, so re-running a stage skips work already done.

### Launch the app

```bash
streamlit run frontend/app.py
```

Open the URL Streamlit prints (typically `http://localhost:8501`), type a legal question, and click **Ask Question** to get an answer with cited source judgments.

### (Optional) Run the evaluation suite

Runs the RAG pipeline against a fixed set of questions (`evaluation/questions.json`) and writes results/timings to `evaluation/evaluation_results.csv`:

```bash
python -m evaluation.run_evaluation
```

## Tech stack

| Layer | Technology |
|---|---|
| Scraping | `requests`, `BeautifulSoup4` |
| PDF text extraction | `PyMuPDF (fitz)` |
| Chunking | `langchain-text-splitters` |
| Embeddings | `sentence-transformers` (`BAAI/bge-small-en-v1.5`) |
| Vector store | `ChromaDB` (persistent, local) |
| LLM | Google `Gemini 2.5 Flash` |
| Frontend | `Streamlit` |

## Notes

- The scraper respects Indian Kanoon by adding delays between requests and retrying on HTTP 429; be mindful of scrape volume/frequency.
- `GEMINI_API_KEY` is required for both the RAG pipeline and the evaluation script — the app will fail to initialize without it.

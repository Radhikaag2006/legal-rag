"""
This will be the entry point of legal RAG scraper.

Workflow :
1. Search Judgements
2. Download PDF's 
3. Parse metadata 
4. Sace metadata as CSV
"""
import time 
from constants import SEARCH_CATEGORIES
from scraper.search import search_judgements
from scraper.downloader import download_all_pdfs
from scraper.parser import parse_all_judgements
from scraper.csv_writer import write_csv
from scraper.checkpoint import(initialize_checkpoint, sync_existing_pdfs, load_checkpoint, filter_completed_judgements)

def main():


    #INITIALISING THE CHECKPOINT 
    
    initialize_checkpoint()
    checkpoint = load_checkpoint()

    if len(checkpoint) == 0:
        print("\n Checkpoint is empty.")
        print("Synchronizing existing PDFs...\n")

        sync_existing_pdfs()

    # START SCRAPING 
    all_results = []

    #loop through every category 
    for category , details in SEARCH_CATEGORIES.items():

        search_query = details["query"]
        max_results = details["max_results"]

        print("\n" + "=" * 70)
        print(f"Category      : {category}")
        print(f"Search Query  : {search_query}")
        print(f"Max Results   : {max_results}")
        print("=" * 70)


        # ---------------------------------------------------------
        # STEP 1 : Search
        # ---------------------------------------------------------

        results = search_judgements(
            search_query=search_query,
            category=category,
            max_results=max_results
        )

        print(f"Found {len(results)} judgments.")

        #Remove judgements already  completed
        results = filter_completed_judgements(results)

        print(f"Judgements left to process : {len(results)}")

        # ---------------------------------------------------------
        # STEP 2 : Download PDFs
        # ---------------------------------------------------------

        results = download_all_pdfs(results)
        print("\nCooling down for one minute before parsing...")
        time.sleep(60)


        # ---------------------------------------------------------
        # STEP 3 : Parse Metadata
        # ---------------------------------------------------------

        results = parse_all_judgements(results)

        # Store results from this category
        all_results.extend(results)
        print("\nWaiting before moving to the next category...")
        time.sleep(60)

    # ---------------------------------------------------------
    # STEP 4 : Save one combined CSV
    # ---------------------------------------------------------

    print("\nSaving CSV...")

    write_csv(all_results)

    print("\n" + "=" * 70)
    print(f"Total judgments scraped : {len(all_results)}")
    print("Legal RAG scraping completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
        
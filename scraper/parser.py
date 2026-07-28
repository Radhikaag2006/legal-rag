# This Extracts additional metadata from the judgement pages

import requests
import time 
from bs4 import BeautifulSoup
from datetime import datetime 
from constants import HEADERS, REQUEST_DELAY,MAX_RETRIES,RETRY_DELAY

#  importing checkpoints 
from scraper.checkpoint import(is_parsed, mark_parsed)

# STEP 1: Fetch Judgement HTML 

def fetch_judgement_html(source_url):
    """
    Downloads the HTML of a judgment page.
    """

    for attempt in range(MAX_RETRIES):

        try:

            response = requests.get(
                source_url,
                headers=HEADERS,
                timeout=30
            )

            # Handle rate limiting
            if response.status_code == 429:

                print(
                    f"Rate limit reached. Waiting {RETRY_DELAY} seconds..."
                )

                time.sleep(RETRY_DELAY)

                continue

            response.raise_for_status()

            # Small delay before next request
            time.sleep(REQUEST_DELAY)

            return response.text

        except requests.exceptions.RequestException as e:

            print(f"Error fetching judgement page: {e}")

            return None

    return None
    
# STEP 2: Parse HTML

def parse_html(html):
    """
    Converts HTML into BeautifulSoup object ."""
    return BeautifulSoup(html, "lxml")

#STEP 3: Extract Judgement Date
def extract_judgement_date(soup):
    """
    Extracts judgement data from the case title.
    """

    title = soup.find("title")
    if title :

        text = title.get_text(strip =   True)

        if "on" in text:
            return text.split("on")[-1].strip()

    return None 

#step 4: extract Judges 
def extract_judges(soup):
    """
    Extract all judges from the Bench.
    """

    judges = []

    bench = soup.find("h3", class_="doc_bench")

    if bench is None:
        return judges

    judge_links = bench.find_all("a")

    for judge in judge_links:

        name = judge.get_text(strip=True)

        if name:
            judges.append(name)

    return judges

# STEP 5 : Extract Citations 
def extract_citations(soup):
    """
    Extract equivalent citations.
    """

    citation_tag = soup.find("h3", class_="doc_citations")

    if citation_tag is None:
        return []

    # Get the complete citation text
    text = citation_tag.get_text(strip=True)

    # Remove the heading
    text = text.replace("Equivalent citations:", "").strip()

    # Use a set to remove duplicates
    citations = set()

    # Split the citations
    for citation in text.split(","):

        citation = citation.strip()

        if citation:
            citations.add(citation)

    return sorted(list(citations))
# STEP - 6: Parse One Judgement 

def parse_judgement(metadata):

    document_id = metadata["document_id"]

    if is_parsed(document_id):
        print(f"Skipping parsing: {document_id}")
        return metadata

    """ Updates one metadata dictionary"""
    html = fetch_judgement_html(metadata["source_url"])

    

    if html is None: 
        return metadata
    
    with open("judgment_page.html", "w", encoding="utf-8") as f:
        f.write(html)

    soup = parse_html(html)

    metadata["judgement_date"] = extract_judgement_date(soup)
    metadata["judges"] = extract_judges(soup)
    metadata["citations"] = extract_citations(soup)

    # Store the timestamp when this judgment was scraped
    metadata["scraped_at"] = datetime.now().isoformat()
    mark_parsed(document_id)
    
    return metadata


#STEP 7 : Parse All Judgements 

def parse_all_judgements(metadata_list):

    """ Update every metadat dictionary."""
    updated = []
    for metadata in metadata_list:

        print(f"Parsing {metadata['document_id']}....")

        updated.append(parse_judgement(metadata))

        # Pause before parsing the next judgment
        time.sleep(REQUEST_DELAY)
    return  updated 

# TESTING 
if __name__ == "__main__":

    from scraper.search import search_judgements
    from scraper.downloader import download_all_pdfs

    results = search_judgements(
        "criminal appeal",
        "Criminal"
    )

    results = download_all_pdfs(results[:2])

    results = parse_all_judgements(results)

    for result in results:

        print()

        print(result)
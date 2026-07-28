import requests
import time 
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from constants import (
    BASE_URL,
    DOCUMENT_TYPE,
    HEADERS,
    REQUEST_DELAY,
    MAX_RETRIES,
    RETRY_DELAY
)

# this function will create the SEARCH URL for a given category

# STEP 1: BUILD SEARCH URL 

def build_search_url(search_query: str, page: int = 0) -> str:
    """
    Builds the search URL for a given query and page number.

    Parameters
    ----------
    search_query : str
    page : int
        Page number starting from 0.

    Returns
    -------
    str
    """

    encoded_query = quote_plus(search_query)

    search_url = (
        f"{BASE_URL}/search/?formInput="
        f"{encoded_query}+doctypes:{DOCUMENT_TYPE}"
        f"&pagenum={page}"
    )

    return search_url

# STEP 2: Download Search Page 
# defining function that will send HTTP requests 
def fetch_search_page(search_query: str, page: int):

    url = build_search_url(search_query, page)

    for attempt in range(MAX_RETRIES):

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            # Handle rate limit
            if response.status_code == 429:

                print(
                    f"Rate limit hit. Waiting {RETRY_DELAY} seconds..."
                )

                time.sleep(RETRY_DELAY)

                continue

            response.raise_for_status()

            time.sleep(REQUEST_DELAY)

            return response

        except requests.exceptions.RequestException as e:

            print(f"Error while fetching search page: {e}")

            return None

    return None

# now we will use Beautiful Soup to parse the HTML stored in response 
# STEP 3: Parse HTML
def parse_search_page(html : str):

    """
    Converts HTML into BeautifulSoup object 
    input : html : by Indian Kanoon 
    Returns : Parsed HTML document 
    """

    soup = BeautifulSoup(html, "lxml")

    return soup


# defining the extract_result_card function 
# STEP 4: EXTRACT SEARCH RESULT CARDS 
def extract_result_cards(soup):
    """
    Extract all the search result cards from the page 

    Input : soup: BeautifulSoup , Parsed HTML page .
    Returns : list -> List of article tags.
    """

    cards = soup.find_all("article"  , class_ = "result")

    return cards

# STEP 5: eXTRACT METADATA FROM 1 CARD
def extract_metadata(card, category, search_query):
    """ extrcat metadata from single search result card."""

    metadata = {
        "document_id":None,
        "case_name":None,
        "court":None,
        "judgement_date":None,
        "category":category ,
        "search_query":search_query,
        "source_url":None,
        "judges" :[],
        "citations": [],
        "pdf_path" : None,
        "scraped_at" : None
    }

    # Extract Case Title 
    title_tag = card.find("h4", class_="result_title")

    if title_tag:
        metadata["case_name"] = title_tag.get_text(strip = True)

    #Extract Court Name 
    court_tag = card.find("span", class_="docsource")
    if court_tag : 
        metadata["court"] = court_tag.get_text(strip = True)

    # Find full document link 
    full_document = None 
    links = card.find_all("a")

    for link in links :

        href = link.get("href","")
        #print(href)

        if href.startswith("/doc/"):
            full_document = href
            break

    # extract documnet ID 
    if full_document :

        document_id = full_document.split("/")[2]
        metadata["document_id"] = document_id
        metadata["source_url"] = BASE_URL + full_document
    return metadata

# STEP 6: SEARCH JUDGEMENT FUNCTION -> IT CALLS ALL THE OTHER FUINCTIONS IN CORRECT 0RDER
def search_judgements(search_query, category, max_results):
    """
    Complete search pipeline.

    Downloads multiple search pages until the required
    number of judgments is collected.
    """

    results = []

    page = 0

    # Keep searching until we collect enough judgments
    while len(results) < max_results:

        print(f"Searching page {page + 1}...")

        response = fetch_search_page(
            search_query,
            page
        )

        if response is None:
            break

        soup = parse_search_page(response.text)

        cards = extract_result_cards(soup)

        # No more search results
        if len(cards) == 0:
            print("No more search results found.")
            break

        for card in cards:

            metadata = extract_metadata(
                card,
                category,
                search_query
            )

            results.append(metadata)

            # Stop exactly at max_results
            if len(results) >= max_results:
                break

        # Move to next page
        page += 1

    return results

# testing 
if __name__ == "__main__":

    results = search_judgements(
        search_query="criminal appeal",
        category="Criminal",
        max_results=30
    )

    print(f"\nTotal Results: {len(results)}\n")

    for i, result in enumerate(results):

        print(f"{i+1}. {result['case_name']}")
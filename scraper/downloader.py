"""
downloader.py

Downloads judgment PDFs from Indian Kanoon.
"""

import os
import time 
import requests
from bs4 import BeautifulSoup

from constants import HEADERS, REQUEST_DELAY, MAX_RETRIES, RETRY_DELAY

#importing the checkpoints 
from scraper.checkpoint import(is_pdf_downloaded, mark_pdf_download)



# ---------------------------------------------------------
# STEP 1 : Create Session
# ---------------------------------------------------------

def create_session():
    """
    Creates a requests session.

    The session automatically stores cookies and
    reuses the same connection for multiple requests.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    return session


# ---------------------------------------------------------
# STEP 2 : Fetch Judgment Page
# ---------------------------------------------------------

def fetch_judgment_page(session, source_url):
    """
    Downloads the HTML of a judgment page.

    Parameters
    ----------
    session : requests.Session

    source_url : str

    Returns
    -------
    Response object
    """

    for attempt in range(MAX_RETRIES):

            try:

                response = session.get(
                    source_url,
                    timeout=30
                )

                # Rate limit hit
                if response.status_code == 429:

                    print(
                        f"Rate limit reached. Waiting {RETRY_DELAY} seconds..."
                    )

                    time.sleep(RETRY_DELAY)

                    continue

                response.raise_for_status()

                # Small delay before next request
                time.sleep(REQUEST_DELAY)

                return response

            except requests.exceptions.RequestException as e:

                print(f"Error fetching judgment page: {e}")

                return None

    return None


# ---------------------------------------------------------
# STEP 3 : Extract CSRF Token
# ---------------------------------------------------------

def extract_csrf_token(html):
    """
    Extracts the CSRF token from the judgment page.
    """

    soup = BeautifulSoup(html, "lxml")

    csrf_input = soup.find(
        "input",
        attrs={"name": "csrfmiddlewaretoken"}
    )

    if csrf_input:
        return csrf_input.get("value")

    return None


# ---------------------------------------------------------
# STEP 4 : Request PDF
# ---------------------------------------------------------

def request_pdf(session, source_url, csrf_token):
    """
    Downloads the PDF from Indian Kanoon.

    Parameters
    ----------
    session : requests.Session

    source_url : str

    csrf_token : str

    Returns
    -------
    Response containing PDF bytes.
    """

    payload = {
        "csrfmiddlewaretoken": csrf_token,
        "type": "pdf"
    }

    headers = {
        "Referer": source_url,
        "Origin": "https://indiankanoon.org",
        "X-CSRFToken": session.cookies.get("csrftoken")
    }

    for attempt in range(MAX_RETRIES):

        try:

            response = session.post(
                source_url,
                data=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 429:

                print(
                    f"Rate limit reached. Waiting {RETRY_DELAY} seconds..."
                )

                time.sleep(RETRY_DELAY)

                continue

            response.raise_for_status()

            # Small delay
            time.sleep(REQUEST_DELAY)

            return response

        except requests.exceptions.RequestException as e:

            print(f"Error downloading PDF: {e}")

            return None

    return None


# ---------------------------------------------------------
# STEP 5 : Save PDF
# ---------------------------------------------------------

def save_pdf(pdf_response, document_id):
    """
    Saves the downloaded PDF to disk.

    Parameters
    ----------
    pdf_response : requests.Response

    document_id : str

    Returns
    -------
    str
        Path where PDF is stored.
    """

    os.makedirs("data/pdfs", exist_ok=True)

    pdf_path = f"data/pdfs/{document_id}.pdf"

    with open(pdf_path, "wb") as file:
        file.write(pdf_response.content)

    return pdf_path

# ---------------------------------------------------------
# STEP 6 : Download One PDF
# ---------------------------------------------------------

def download_pdf(session, metadata):
    """
    Downloads the PDF for one judgment.

    Parameters
    ----------
    session : requests.Session

    metadata : dict

    Returns
    -------
    dict
        Updated metadata dictionary.
    """

    source_url = metadata["source_url"]
    document_id = metadata["document_id"]

    # --------------------------------------------------
    # Check if PDF is already downloaded
    # --------------------------------------------------

    pdf_path = f"data/pdfs/{document_id}.pdf"

    if is_pdf_downloaded(document_id) and os.path.exists(pdf_path):
        metadata["pdf_path"] = pdf_path
        print(f"PDF already exists: {document_id}")
        return metadata

    # --------------------------------------------------
    # Fetch judgment page
    # --------------------------------------------------

    # Download HTML page
    page = fetch_judgment_page(
        session,
        source_url
    )

    if page is None:
        return metadata

    # Extract CSRF token
    csrf_token = extract_csrf_token(page.text)

    if csrf_token is None:
        print(f"CSRF token not found for {document_id}")
        return metadata

    # Download PDF
    pdf_response = request_pdf(
        session,
        source_url,
        csrf_token
    )

    if pdf_response is None:
        return metadata

    # Save PDF
    pdf_path = save_pdf(
        pdf_response,
        document_id
    )

    # Update metadata dictionary
    metadata["pdf_path"] = pdf_path

    #Update  checkpoint 
    mark_pdf_download(document_id)

    return metadata

# ---------------------------------------------------------
# STEP 7 : Download All PDFs
# ---------------------------------------------------------

def download_all_pdfs(metadata_list):
    """
    Downloads PDFs for all judgments.

    Parameters
    ----------
    metadata_list : list

    Returns
    -------
    list
        Updated metadata dictionaries.
    """

    session = create_session()

    updated_results = []

    for metadata in metadata_list:

        print(f"Downloading PDF for {metadata['document_id']}...")

        updated_metadata = download_pdf(
            session,
            metadata
        )

        updated_results.append(updated_metadata)

        # Pause before downloading the next PDF
        time.sleep(REQUEST_DELAY)

    return updated_results

# ---------------------------------------------------------
# TESTING
# ---------------------------------------------------------

from scraper.search import search_judgements

if __name__ == "__main__":

    results = search_judgements(
        search_query="criminal appeal",
        category="Criminal",
        max_results = 2
    )

    updated_results = download_all_pdfs(results[:2])

    for result in updated_results:
        print(result)
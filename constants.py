"""
constants.py

Stores all project-wide constants.
"""

# ---------------------------------------------------------
# Base URL
# ---------------------------------------------------------

BASE_URL = "https://indiankanoon.org"

# ---------------------------------------------------------
# We are scraping only judgments
# ---------------------------------------------------------

DOCUMENT_TYPE = "judgments"

# ---------------------------------------------------------
# Browser Headers
# ---------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
}

# ---------------------------------------------------------
# Number of search results shown on one page
# ---------------------------------------------------------

RESULTS_PER_PAGE = 10

# ---------------------------------------------------------
# Search Categories
# ---------------------------------------------------------

SEARCH_CATEGORIES = {

    "Criminal": {
        "query": "criminal appeal",
        "max_results": 30
    },

    "Civil": {
        "query": "civil suit",
        "max_results": 30
    },

    "Constitutional": {
        "query": "constitutional law",
        "max_results": 30
    },

    "Tax": {
        "query": "income tax",
        "max_results": 30
    },

    "Corporate": {
        "query": "company law",
        "max_results": 30
    }

}


# ---------------------------------------------------------
# Request Configuration
# ---------------------------------------------------------

REQUEST_DELAY = 5 # Seconds between requests

MAX_RETRIES = 5  # Retry attempts for HTTP 429

RETRY_DELAY = 60 # Wait 30 seconds before retrying
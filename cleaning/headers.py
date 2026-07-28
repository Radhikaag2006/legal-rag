from cleaning.patterns import (
    DOWNLOAD_PATTERN,
    KANOON_URL_PATTERN,
    PAGE_PATTERN,
    SEPARATOR_PATTERN
)

from cleaning.patterns import STANDALONE_PAGE_NUMBER

def remove_download_information(text: str) -> str:
    """
    Remove 'Downloaded on ...'
    """

    return DOWNLOAD_PATTERN.sub(
        "",
        text
    )


def remove_kanoon_urls(text: str) -> str:
    """
    Remove Indian Kanoon footer/header.
    """

    return KANOON_URL_PATTERN.sub(
        "",
        text
    )


def remove_page_numbers(text: str) -> str:
    """
    Remove page numbers.
    """

    return PAGE_PATTERN.sub(
        "",
        text
    )


def remove_separator_lines(text: str) -> str:
    """
    Remove long separator lines.
    """

    return SEPARATOR_PATTERN.sub(
        "",
        text
    )

def remove_standalone_page_numbers(text: str) -> str:
   return STANDALONE_PAGE_NUMBER.sub("", text)


def remove_headers_and_footers(text: str) -> str:
    """
    Apply all header/footer cleaning.
    """

    text = remove_download_information(text)

    text = remove_kanoon_urls(text)

    text = remove_page_numbers(text)

    text = remove_separator_lines(text)
    text = remove_standalone_page_numbers(text)

    return text
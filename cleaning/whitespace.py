from .patterns import (
    MULTIPLE_NEWLINES,
    MULTIPLE_SPACES
)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace while preserving paragraph breaks.
    """

    # Remove trailing spaces
    lines = [
        line.strip()
        for line in text.splitlines()
    ]

    text = "\n".join(lines)

    # Collapse repeated spaces
    text = MULTIPLE_SPACES.sub(
        " ",
        text
    )

    # Collapse repeated blank lines
    text = MULTIPLE_NEWLINES.sub(
        "\n\n",
        text
    )

    return text.strip()
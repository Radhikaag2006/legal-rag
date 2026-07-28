import re

# =====================================================
# Indian Kanoon Patterns
# =====================================================

DOWNLOAD_PATTERN = re.compile(
    r"Downloaded on.*",
    re.IGNORECASE
)

KANOON_URL_PATTERN = re.compile(
    r"Indian Kanoon.*",
    re.IGNORECASE
)
STANDALONE_PAGE_NUMBER = re.compile(r"^\d+\s*$", re.MULTILINE)
# =====================================================
# Page Numbers
# =====================================================

PAGE_PATTERN = re.compile(
    r"^\s*Page\s+\d+\s*$",
    re.IGNORECASE | re.MULTILINE
)

# =====================================================
# Separator Lines
# =====================================================

SEPARATOR_PATTERN = re.compile(
    r"[-_=]{3,}"
)

# =====================================================
# Multiple Blank Lines
# =====================================================

MULTIPLE_NEWLINES = re.compile(
    r"\n{3,}"
)

# =====================================================
# Multiple Spaces
# =====================================================

MULTIPLE_SPACES = re.compile(
    r"[ \t]{2,}"
)
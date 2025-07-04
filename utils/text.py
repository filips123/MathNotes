import re

import unidecode


def slugify(text: str):
    """Convert a string to a filename-friendly slug."""

    text = unidecode.unidecode(text).lower()
    return re.sub(r"[\W_]+", "-", text)

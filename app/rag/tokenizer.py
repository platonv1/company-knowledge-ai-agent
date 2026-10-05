"""Token counting.

Chunk sizes are measured in tokens rather than characters because the context
budget is in tokens; a character-based limit over-packs dense tables and
under-packs prose.
"""

from functools import lru_cache

import tiktoken

ENCODING = "cl100k_base"


@lru_cache(maxsize=1)
def _encoder() -> "tiktoken.Encoding":
    return tiktoken.get_encoding(ENCODING)


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_encoder().encode(text))


def take_last_tokens(text: str, limit: int) -> str:
    """Return the trailing `limit` tokens of `text`, used to build chunk overlap."""
    if limit <= 0 or not text:
        return ""
    encoder = _encoder()
    tokens = encoder.encode(text)
    if len(tokens) <= limit:
        return text
    return encoder.decode(tokens[-limit:])


def split_by_tokens(text: str, limit: int) -> list[str]:
    """Hard-split text into pieces of at most `limit` tokens.

    Last resort for a single sentence longer than a whole chunk.
    """
    encoder = _encoder()
    tokens = encoder.encode(text)
    return [encoder.decode(tokens[i : i + limit]) for i in range(0, len(tokens), limit)]

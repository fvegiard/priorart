"""Shared limits and publish locations."""

REPO = "fvegiard/priorart"
INDEX_TAG = "index-latest"
INDEX_FILENAME = "priorart-index.json"
MANIFEST_FILENAME = "priorart-index-manifest.json"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
HASH_EMBEDDING_MODEL = "hash-bow"
HASH_EMBEDDING_DIM = 64
INDEX_SCHEMA_VERSION = 1
MIN_REAL_SOURCES = 25
COMMUNITY_MAX_AGE_DAYS = 92
REFRESH_MAX_DAYS = 35
NOTE_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


def release_asset_url(tag: str, filename: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{tag}/{filename}"


DEFAULT_INDEX_URL = release_asset_url(INDEX_TAG, INDEX_FILENAME)
DEFAULT_MANIFEST_URL = release_asset_url(INDEX_TAG, MANIFEST_FILENAME)
PAGES_URL = f"https://{REPO.split('/')[0]}.github.io/{REPO.split('/')[1]}/"

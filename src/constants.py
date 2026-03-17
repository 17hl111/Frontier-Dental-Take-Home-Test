"""This module exists to centralize shared constants like HTTP headers and page type labels. 
It keeps magic strings out of the agents and fetcher to reduce duplication. 
Possible improvement: make these values configurable per site."""

DEFAULT_HEADERS = {
    # Baseline headers to reduce basic bot blocking and caching artifacts.
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# Page type labels used by the classifier and downstream logic.
PAGE_TYPE_CATEGORY = "category_listing"
PAGE_TYPE_PRODUCT = "product_detail"
PAGE_TYPE_UNKNOWN = "unknown"
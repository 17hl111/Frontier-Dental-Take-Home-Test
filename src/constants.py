# Summary: Shared constants used across scraping and classification logic.

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

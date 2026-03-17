"""This module exists to centralize CSS selectors used by the scraper. It keeps selector changes localized and easy to update. Possible improvement: make selectors site configurable instead of hard coded, but that is future work."""

CATEGORY_PRODUCT_LINK_SELECTORS = [
    "a[href*='/product/']",
    "a.product-item-link",
    ".product-item-info a",
    "a.product.name.product-item-name",
    "a[href*='trade-']",
]

# Next-page selectors for category listings.
CATEGORY_NEXT_PAGE_SELECTORS = [
    "a.next",
    "li.item.pages-item-next a",
    "a.action.next",
    "a[rel='next']",
    ".pages-item-next a",
]

# Title selectors for product detail pages.
PRODUCT_TITLE_SELECTORS = [
    "h1.page-title span.base",
    "h1.page-title",
    "h1[itemprop='name']",
    "main h1",
    "h1",
]

# Price selectors for product detail pages.
PRODUCT_PRICE_SELECTORS = [
    ".product-info-price .price",
    ".price-box .price",
    "[data-price-type='finalPrice'] .price",
    ".price-wrapper .price",
    "span.price",
]

# Description selectors for product detail pages.
PRODUCT_DESCRIPTION_SELECTORS = [
    ".product.attribute.description .value",
    ".product.attribute.overview .value",
    "#description .value",
    "[itemprop='description']",
    ".product.attribute.description",
    "#product-details-tab-description",
]

# Image selectors for product detail pages.
PRODUCT_IMAGE_SELECTORS = [
    ".fotorama__stage img",
    ".gallery-placeholder img",
    "img.fotorama__img",
    "img[itemprop='image']",
    ".product.media img",
]

# Related product link selectors for cross-sell/upsell blocks.
PRODUCT_RELATED_LINK_SELECTORS = [
    ".block.related a[href*='/product/']",
    ".products-related a[href*='/product/']",
    ".product-item a[href*='/product/']",
    ".upsell a[href*='/product/']",
]

# Table selectors for specs when present.
SPEC_TABLE_SELECTORS = [
    "table",
    ".additional-attributes table",
    "#product-attribute-specs-table",
]
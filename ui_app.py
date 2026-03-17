"""This module exists to provide a simple Streamlit UI for the scraper. It allows category discovery, selection, run control, and output review without the CLI. Possible improvement: add pagination for large outputs and richer progress reporting, but that is out of scope."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.runner import Runner

# Defaults provide a quick start when discovery is not used.
DEFAULT_CATEGORIES = [
    {
        "name": "Dental Exam Gloves",
        "url": "https://www.safcodental.com/catalog/gloves",
    },
    {
        "name": "Sutures & Surgical Products",
        "url": "https://www.safcodental.com/catalog/sutures-surgical-products",
    },
]

DEFAULT_MAX_PRODUCTS = 4
DEFAULT_MAX_PAGES = 1


def init_state() -> None:
    # Initialize discovery results and selection state.
    if "discovered_categories" not in st.session_state:
        st.session_state.discovered_categories = []


def collect_selected_categories() -> list[dict]:
    # Build the selected category list from checkbox state.
    selected: list[dict] = []
    for idx, item in enumerate(st.session_state.discovered_categories):
        if st.session_state.get(f"cat_select_{idx}", False):
            selected.append({"name": item["name"], "url": item["url"]})
    return selected


def render_file_status(path_str: str) -> None:
    # Show a simple status indicator for generated files.
    path = Path(path_str)
    if path.exists():
        st.success(f"Generated: {path_str}")
    else:
        st.info(f"Not generated: {path_str}")


def main() -> None:
    # Page configuration and base layout.
    st.set_page_config(page_title="Frontier Safco Scraper UI", layout="wide")
    init_state()

    st.title("Frontier Safco Scraper UI")
    st.caption("Configure categories, run the scraper, review outputs, and clean previous artifacts.")

    st.subheader("Categories")
    col_discover, _ = st.columns([1, 3])
    with col_discover:
        discover_clicked = st.button("Discover Categories", use_container_width=True)

    if discover_clicked:
        try:
            runner = Runner()
            st.session_state.discovered_categories = runner.discover_categories()
            for idx in range(len(st.session_state.discovered_categories)):
                st.session_state[f"cat_select_{idx}"] = False
        except Exception as exc:
            st.error(f"Discovery failed: {exc}")

    if st.session_state.discovered_categories:
        st.caption(f"Discovered {len(st.session_state.discovered_categories)} categories. Select the ones to crawl.")
        for idx, item in enumerate(st.session_state.discovered_categories):
            label = f"{item['name']}  |  {item['url']}"
            st.checkbox(label, value=st.session_state.get(f"cat_select_{idx}", False), key=f"cat_select_{idx}")
    else:
        st.info("No categories discovered yet. Click Discover Categories.")

    st.subheader("Run Settings")
    col_mp, col_pg, col_fr = st.columns([1, 1, 1])

    with col_mp:
        max_products = st.number_input(
            "Max Products per Category",
            min_value=1,
            value=DEFAULT_MAX_PRODUCTS,
            step=1,
        )

    with col_pg:
        max_pages = st.number_input(
            "Max Pages per Category",
            min_value=1,
            value=DEFAULT_MAX_PAGES,
            step=1,
        )

    with col_fr:
        fresh_run = st.checkbox("Fresh Run", value=True)

    st.subheader("Actions")
    col_run, col_clean = st.columns([2, 1])

    with col_run:
        run_clicked = st.button("Run Scraper", use_container_width=True, type="primary")

    with col_clean:
        clean_clicked = st.button("Clean Previous Outputs", use_container_width=True)

    if clean_clicked:
        try:
            runner = Runner()
            cleanup_result = runner.cleanup_environment()
            st.success("Cleanup completed.")
            st.json(cleanup_result)
        except Exception as exc:
            st.error(f"Cleanup failed: {exc}")

    if run_clicked:
        if st.session_state.discovered_categories:
            categories_override = collect_selected_categories()
            if not categories_override:
                st.warning("Select at least one discovered category before running.")
                return
        else:
            categories_override = [dict(item) for item in DEFAULT_CATEGORIES]

        try:
            with st.spinner("Running scraper..."):
                runner = Runner()
                stats = runner.run(
                    max_products=int(max_products),
                    max_pages=int(max_pages),
                    fresh=bool(fresh_run),
                    categories_override=categories_override,
                )

            st.success("Run completed.")
            st.subheader("Run Stats")
            st.json(stats)

            st.subheader("Generated Files")
            render_file_status("output/sample_products.json")
            render_file_status("output/sample_products.csv")
            render_file_status("output/safco_products.db")
            render_file_status("output/qa_review_report.json")
            render_file_status("output/crawl_quality_summary.json")

            products_path = Path("output/sample_products.json")
            qa_path = Path("output/qa_review_report.json")
            summary_path = Path("output/crawl_quality_summary.json")

            if products_path.exists():
                # Show the full product list for transparency.
                st.subheader("Products Preview")
                products = json.loads(products_path.read_text(encoding="utf-8"))
                st.json(products if isinstance(products, list) else products)

            if qa_path.exists():
                st.subheader("QA Review Report")
                qa_data = json.loads(qa_path.read_text(encoding="utf-8"))
                st.json(qa_data)

            if summary_path.exists():
                st.subheader("Crawl Quality Summary")
                summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
                st.json(summary_data)

        except Exception as exc:
            st.error(f"Run failed: {exc}")


if __name__ == "__main__":
    main()
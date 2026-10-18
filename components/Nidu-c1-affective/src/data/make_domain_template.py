"""
src/data/make_domain_template.py

Utility script to generate standardized domain annotation templates for human annotators.
Outputs template CSVs conforming to the C1 annotation protocol (docs/annotation_guide.md).
"""

import argparse
import logging
from pathlib import Path
from typing import List, Optional
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("make_domain_template")

TEMPLATE_COLUMNS = [
    "text",
    "label",
    "annotator",
    "confidence",
    "notes",
    "source",
    "reviewed",
]


def generate_empty_template(
    output_path: Path,
    num_blank_rows: int = 10,
) -> Path:
    """Creates a blank domain annotation template with pre-filled column headers."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for _ in range(num_blank_rows):
        rows.append({
            "text": "",
            "label": "",
            "annotator": "",
            "confidence": "",
            "notes": "",
            "source": "domain",
            "reviewed": False,
        })
    df = pd.DataFrame(rows, columns=TEMPLATE_COLUMNS)
    df.to_csv(output_path, index=False)
    logger.info(f"Blank template with {len(df)} rows created at: {output_path}")
    return output_path


def format_unlabelled_texts_for_annotation(
    texts: List[str],
    output_path: Path,
    source_tag: str = "domain",
) -> Path:
    """Takes a list of raw unlabelled student texts and formats them into the annotation template."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for t in texts:
        cleaned_text = str(t).strip()
        if not cleaned_text:
            continue
        rows.append({
            "text": cleaned_text,
            "label": "",
            "annotator": "",
            "confidence": "",
            "notes": "",
            "source": source_tag,
            "reviewed": False,
        })
    df = pd.DataFrame(rows, columns=TEMPLATE_COLUMNS)
    df.to_csv(output_path, index=False)
    logger.info(f"Annotation template populated with {len(df)} candidate items at: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Create domain annotation template CSV for C1")
    parser.add_argument(
        "--output",
        type=str,
        default="data/interim/domain_annotation_template.csv",
        help="Target output CSV path",
    )
    parser.add_argument(
        "--input-texts",
        type=str,
        default=None,
        help="Optional input CSV or text file containing raw unlabelled texts",
    )
    parser.add_argument(
        "--num-rows",
        type=int,
        default=20,
        help="Number of blank rows if creating empty template",
    )
    args = parser.parse_args()

    component_root = Path(__file__).resolve().parents[2]
    out_path = component_root / args.output

    if args.input_texts:
        inp = Path(args.input_texts)
        if not inp.is_absolute():
            inp = component_root / args.input_texts
        if inp.suffix.lower() == ".csv":
            df_in = pd.read_csv(inp)
            text_col = "text" if "text" in df_in.columns else df_in.columns[0]
            texts = df_in[text_col].dropna().tolist()
        else:
            with open(inp, "r", encoding="utf-8") as f:
                texts = [line.strip() for line in f if line.strip()]
        format_unlabelled_texts_for_annotation(texts, out_path)
    else:
        generate_empty_template(out_path, num_blank_rows=args.num_rows)


if __name__ == "__main__":
    main()

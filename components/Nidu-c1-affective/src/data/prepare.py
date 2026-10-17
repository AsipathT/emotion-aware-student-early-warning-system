"""
src/data/prepare.py

Data Pipeline for Component 1: Affective State Detection.
Preprocesses external proxy corpora (GoEmotions and Emotion-4) into 
multi-label format (5 academic distress classes).

Enforces:
1. Ignore-label rule: if a sample has an ignore label AND a mapped distress label,
   KEEP it with the distress labels as positives. Exclude only samples whose labels
   are ignore-only (or ignore plus unmapped).
2. Text normalization: cleans tweet/social artefacts (URLs, user mentions, hashtags).
3. Leakage prevention: deduplicates texts and drops any cross-split duplicate from train.
4. Preserves official GoEmotions train/dev/test splits; splits Emotion-4 80/10/10 (seed 42).
5. Computes positive class weights (pos_weight) on train split only (clipped at 10.0).
6. Outputs train.csv, val.csv, and test_proxy.csv.
"""

import argparse
import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("c1_data_prepare")

# ── Text Normalization Regex ────────────────────────────────────────────────
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
MENTION_PATTERN = re.compile(r"(?:@[\w-]+|/?u/[\w-]+)", re.IGNORECASE)
HASHTAG_PATTERN = re.compile(r"#([\w-]+)")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """
    Standardizes social media / tweet artefacts into neutral tokens:
    - Replaces URLs with [URL]
    - Replaces user mentions (@user, /u/user) with [USER]
    - Strips hashtag prefix # but keeps the token word
    - Collapses consecutive whitespace
    """
    if not isinstance(text, str):
        return ""
    text = URL_PATTERN.sub("[URL]", text)
    text = MENTION_PATTERN.sub("[USER]", text)
    text = HASHTAG_PATTERN.sub(r"\1", text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def load_label_map(label_map_path: Path) -> Tuple[List[str], Dict[str, str], Set[str], Set[str]]:
    """Loads label_map.yaml and partitions emotions into target classes, ignore set, and unmapped set."""
    with open(label_map_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    target_classes = config["target_classes"]
    goemotions_cfg = config["goemotions"]

    distress_map: Dict[str, str] = {}
    ignore_set: Set[str] = set()
    unmapped_set: Set[str] = set()

    for emo, spec in goemotions_cfg.items():
        m_type = spec.get("mapping_type")
        tgt = spec.get("target")
        if tgt and m_type == "proxy":
            distress_map[emo] = tgt
        elif m_type == "ignore":
            ignore_set.add(emo)
        else:
            unmapped_set.add(emo)

    return target_classes, distress_map, ignore_set, unmapped_set


def process_goemotions_split(
    tsv_path: Path,
    emotions_txt: Path,
    target_classes: List[str],
    distress_map: Dict[str, str],
    ignore_set: Set[str],
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Processes a single GoEmotions TSV split applying the ignore-label rule:
    - If ignore AND distress: KEEP with distress as positive.
    - If ignore AND NOT distress: EXCLUDE.
    - If NO ignore AND distress: KEEP with distress as positive.
    - If NO ignore AND unmapped: KEEP as negative (all zeros).
    """
    with open(emotions_txt, "r", encoding="utf-8") as f:
        all_emotions = [l.strip() for l in f if l.strip()]
    idx2emo = {i: emo for i, emo in enumerate(all_emotions)}

    df_raw = pd.read_csv(tsv_path, sep="\t", header=None, names=["text", "labels", "id"])

    stats = {
        "total_input": len(df_raw),
        "kept_ignore_plus_distress": 0,
        "excluded_ignore_only_or_unmapped": 0,
        "kept_distress_clean": 0,
        "kept_unmapped_clean": 0,
        "total_kept": 0,
    }

    records = []
    for _, row in df_raw.iterrows():
        raw_text = str(row["text"])
        label_ids = [int(x) for x in str(row["labels"]).split(",") if x.strip().isdigit()]
        sample_emos = {idx2emo[i] for i in label_ids if i in idx2emo}

        has_ignore = bool(sample_emos & ignore_set)
        active_distress = {distress_map[e] for e in sample_emos if e in distress_map}
        has_distress = len(active_distress) > 0

        if has_ignore and has_distress:
            # Case A: Ignore + Distress -> KEEP
            stats["kept_ignore_plus_distress"] += 1
            include = True
        elif has_ignore and not has_distress:
            # Case B: Ignore only / ignore + unmapped -> EXCLUDE
            stats["excluded_ignore_only_or_unmapped"] += 1
            include = False
        elif has_distress:
            # Case C1: Clean distress -> KEEP
            stats["kept_distress_clean"] += 1
            include = True
        else:
            # Case C2: Clean unmapped/neutral -> KEEP as negative
            stats["kept_unmapped_clean"] += 1
            include = True

        if include:
            clean_t = normalize_text(raw_text)
            rec = {
                "text": clean_t,
                "source": "goemotions_proxy",
            }
            for cls in target_classes:
                rec[cls] = 1 if cls in active_distress else 0
            records.append(rec)

    stats["total_kept"] = len(records)
    processed_df = pd.DataFrame(records)
    return processed_df, stats


def process_emotion4(
    csv_path: Path,
    target_classes: List[str],
    seed: int = 42,
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    test_ratio: float = 0.10,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, int]]:
    """
    Processes Emotion-4 dataset (eng_dataset.csv):
    - fear -> exam_anxiety = 1
    - anger -> course_frustration = 1
    - sadness -> academic_helplessness = 1
    - joy -> negative baseline (all 0s)
    - Performs 80/10/10 stratified split by sentiment
    """
    df_raw = pd.read_csv(csv_path)
    stats = {"total_input": len(df_raw)}

    mapping = {
        "fear": "exam_anxiety",
        "anger": "course_frustration",
        "sadness": "academic_helplessness",
        "joy": None,
    }

    records = []
    for _, row in df_raw.iterrows():
        sentiment = str(row["sentiment"]).strip().lower()
        if sentiment not in mapping:
            continue
        clean_t = normalize_text(str(row["content"]))
        rec = {
            "text": clean_t,
            "source": "emotion4_proxy",
            "sentiment_str": sentiment,
        }
        target_distress = mapping[sentiment]
        for cls in target_classes:
            rec[cls] = 1 if cls == target_distress else 0
        records.append(rec)

    df_clean = pd.DataFrame(records)
    stats["valid_records"] = len(df_clean)

    # 80/10/10 stratified split
    val_test_size = val_ratio + test_ratio
    train_df, val_test_df = train_test_split(
        df_clean,
        test_size=val_test_size,
        random_state=seed,
        stratify=df_clean["sentiment_str"],
    )

    relative_test_size = test_ratio / val_test_size
    val_df, test_df = train_test_split(
        val_test_df,
        test_size=relative_test_size,
        random_state=seed,
        stratify=val_test_df["sentiment_str"],
    )

    train_df = train_df.drop(columns=["sentiment_str"])
    val_df = val_df.drop(columns=["sentiment_str"])
    test_df = test_df.drop(columns=["sentiment_str"])

    stats["train_count"] = len(train_df)
    stats["val_count"] = len(val_df)
    stats["test_count"] = len(test_df)

    return train_df, val_df, test_df, stats


def deduplicate_and_prevent_leakage(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, int]]:
    """
    Deduplicates texts and ensures zero cross-split data leakage.
    Rules:
    - Intra-split deduplication on dev and test (keeping first).
    - Cross-split resolution: if text appears in train and dev/test, drop from train.
    - If text appears in both dev and test, drop from dev (keeping test intact).
    """
    stats = {}
    init_train_len = len(train_df)
    init_val_len = len(val_df)
    init_test_len = len(test_df)

    # 1. Deduplicate test
    test_clean = test_df.drop_duplicates(subset=["text"], keep="first").copy()
    stats["test_intra_duplicates_dropped"] = init_test_len - len(test_clean)

    # 2. Deduplicate val
    val_clean = val_df.drop_duplicates(subset=["text"], keep="first").copy()
    stats["val_intra_duplicates_dropped"] = init_val_len - len(val_clean)

    # 3. Check val vs test leakage (drop from val)
    test_texts = set(test_clean["text"])
    val_leakage_mask = val_clean["text"].isin(test_texts)
    stats["val_test_leakage_dropped_from_val"] = int(val_leakage_mask.sum())
    val_clean = val_clean[~val_leakage_mask].copy()

    # 4. Check train vs (val | test) leakage (drop from train)
    eval_texts = test_texts | set(val_clean["text"])
    train_leakage_mask = train_df["text"].isin(eval_texts)
    stats["train_eval_leakage_dropped_from_train"] = int(train_leakage_mask.sum())
    train_clean = train_df[~train_leakage_mask].copy()

    # 5. Deduplicate remaining train
    pre_dedup_train_len = len(train_clean)
    train_clean = train_clean.drop_duplicates(subset=["text"], keep="first").copy()
    stats["train_intra_duplicates_dropped"] = pre_dedup_train_len - len(train_clean)

    # Verify zero leakage assertions
    train_set = set(train_clean["text"])
    val_set = set(val_clean["text"])
    test_set = set(test_clean["text"])

    assert len(train_set & val_set) == 0, "Leakage detected between train and val!"
    assert len(train_set & test_set) == 0, "Leakage detected between train and test!"
    assert len(val_set & test_set) == 0, "Leakage detected between val and test!"

    stats["final_train_samples"] = len(train_clean)
    stats["final_val_samples"] = len(val_clean)
    stats["final_test_proxy_samples"] = len(test_clean)

    return train_clean, val_clean, test_clean, stats


def compute_pos_weights(
    train_df: pd.DataFrame, target_classes: List[str], clip_max: float = 10.0
) -> Dict[str, float]:
    """
    Computes positive class weights from the train split only:
    pos_weight = min(N_neg / N_pos, clip_max)
    """
    weights = {}
    total = len(train_df)
    for cls in target_classes:
        pos = int(train_df[cls].sum())
        neg = total - pos
        if pos == 0:
            w = clip_max
        else:
            raw_w = neg / pos
            w = min(raw_w, clip_max)
        weights[cls] = round(float(w), 4)
    return weights


def prepare_datasets(
    component_root: Path,
    max_samples: Optional[int] = None,
    seed: int = 42,
) -> Dict[str, any]:
    """Main execution pipeline."""
    label_map_path = component_root / "src" / "label_map.yaml"
    goemo_dir = component_root / "data" / "raw" / "goemotions"
    emo4_path = component_root / "data" / "raw" / "emotion4" / "eng_dataset.csv"
    processed_dir = component_root / "data" / "processed"
    reports_metrics_dir = component_root / "reports" / "metrics"

    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_metrics_dir.mkdir(parents=True, exist_ok=True)

    target_classes, distress_map, ignore_set, unmapped_set = load_label_map(label_map_path)
    emotions_txt = goemo_dir / "emotions.txt"

    # 1. Process GoEmotions splits
    goemo_dfs = {}
    goemo_stats = {}
    for split in ["train", "dev", "test"]:
        tsv_p = goemo_dir / f"{split}.tsv"
        df, s = process_goemotions_split(tsv_p, emotions_txt, target_classes, distress_map, ignore_set)
        goemo_dfs[split] = df
        goemo_stats[split] = s

    # 2. Process Emotion-4
    emo4_train, emo4_val, emo4_test, emo4_stats = process_emotion4(
        emo4_path, target_classes, seed=seed
    )

    # 3. Concatenate corresponding splits
    train_raw = pd.concat([goemo_dfs["train"], emo4_train], ignore_index=True)
    val_raw = pd.concat([goemo_dfs["dev"], emo4_val], ignore_index=True)
    test_raw = pd.concat([goemo_dfs["test"], emo4_test], ignore_index=True)

    # 4. Deduplicate and eliminate leakage
    train_final, val_final, test_final, dedup_stats = deduplicate_and_prevent_leakage(
        train_raw, val_raw, test_raw
    )

    # Optional smoke-test slicing
    if max_samples and max_samples > 0:
        logger.info(f"Applying smoke-test sampling: max_samples={max_samples}")
        train_final = train_final.iloc[:max_samples].copy()
        val_samples = max(10, int(max_samples * 0.15))
        val_final = val_final.iloc[:val_samples].copy()
        test_final = test_final.iloc[:val_samples].copy()

    # 5. Compute pos_weights strictly on train
    pos_weights = compute_pos_weights(train_final, target_classes, clip_max=10.0)

    # 6. Save processed CSVs
    train_final.to_csv(processed_dir / "train.csv", index=False)
    val_final.to_csv(processed_dir / "val.csv", index=False)
    test_final.to_csv(processed_dir / "test_proxy.csv", index=False)

    # 7. Collect class distributions and summary
    summary = {
        "goemotions_stats": goemo_stats,
        "emotion4_stats": emo4_stats,
        "dedup_stats": dedup_stats,
        "split_counts": {
            "train": len(train_final),
            "val": len(val_final),
            "test_proxy": len(test_final),
        },
        "pos_weights_train": pos_weights,
        "target_classes": target_classes,
        "thresholds_todo": "Tune per-class sigmoid thresholds on val split in Phase 3.",
    }

    class_distribution = {}
    for name, df in [("train", train_final), ("val", val_final), ("test_proxy", test_final)]:
        class_distribution[name] = {cls: int(df[cls].sum()) for cls in target_classes}
        class_distribution[name]["all_zero_negatives"] = int((df[target_classes].sum(axis=1) == 0).sum())
    summary["class_distribution"] = class_distribution

    # Save summary and class_weights JSON
    with open(reports_metrics_dir / "class_weights.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "pos_weights": pos_weights,
                "clip_max": 10.0,
                "note": "Computed on train.csv only. Thresholds to be tuned on val.csv in Phase 3.",
            },
            f,
            indent=2,
        )

    with open(reports_metrics_dir / "data_pipeline_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Prepare data pipeline for C1 Affective State Detection")
    parser.add_argument("--max-samples", type=int, default=None, help="Max samples for smoke testing")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for splitting")
    args = parser.parse_args()

    component_root = Path(__file__).resolve().parents[2]
    summary = prepare_datasets(component_root, max_samples=args.max_samples, seed=args.seed)

    print("\n" + "=" * 60)
    print("DATA PIPELINE SUMMARY (Counts Only - No Raw Text)")
    print("=" * 60)
    print(f"Final Split Counts:")
    for k, v in summary["split_counts"].items():
        print(f"  {k:15s}: {v:6d}")

    print("\nGoEmotions Ignore-Label Dispositions:")
    for split, st in summary["goemotions_stats"].items():
        print(f"  [{split.upper()}] Input: {st['total_input']}")
        print(f"    Case A (Ignore + Distress -> KEPT):    {st['kept_ignore_plus_distress']:6d}")
        print(f"    Case B (Ignore only/unmapped -> DROP): {st['excluded_ignore_only_or_unmapped']:6d}")
        print(f"    Case C1 (Distress clean -> KEPT):      {st['kept_distress_clean']:6d}")
        print(f"    Case C2 (Unmapped clean -> KEPT neg):  {st['kept_unmapped_clean']:6d}")
        print(f"    Total Kept:                            {st['total_kept']:6d}")

    print("\nLeakage Prevention & Deduplication:")
    for k, v in summary["dedup_stats"].items():
        print(f"  {k:40s}: {v}")

    print("\nPositive Class Distribution:")
    for split, dist in summary["class_distribution"].items():
        print(f"  [{split}]:")
        for cls, count in dist.items():
            print(f"    {cls:25s}: {count:5d}")

    print("\nPositive Class Weights (pos_weight from train, clipped at 10.0):")
    for cls, w in summary["pos_weights_train"].items():
        print(f"  {cls:25s}: {w:6.4f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

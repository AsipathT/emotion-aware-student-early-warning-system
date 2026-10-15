import json
from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPONENT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "contracts" / "v1" / "AffectiveWeeklyVector.json"
LABEL_MAP_PATH = COMPONENT_ROOT / "src" / "label_map.yaml"
TAXONOMY_DOC_PATH = COMPONENT_ROOT / "docs" / "taxonomy.md"
GOEMOTIONS_TXT = COMPONENT_ROOT / "data" / "raw" / "goemotions" / "emotions.txt"


@pytest.fixture
def contract_distress_classes():
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        contract = json.load(f)
    return contract["$defs"]["DistressClass"]["enum"]


@pytest.fixture
def label_map():
    with open(LABEL_MAP_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_taxonomy_classes_match_contract(contract_distress_classes, label_map):
    """Verify target_classes in label_map.yaml match the contract DistressClass enum."""
    expected = [
        "exam_anxiety",
        "conceptual_confusion",
        "academic_helplessness",
        "course_frustration",
        "motivation_erosion",
    ]
    assert contract_distress_classes == expected
    assert label_map["target_classes"] == expected


def test_taxonomy_doc_contains_all_classes(contract_distress_classes):
    """Verify docs/taxonomy.md documents all 5 distress classes."""
    with open(TAXONOMY_DOC_PATH, "r", encoding="utf-8") as f:
        doc_text = f.read()
    for cls_name in contract_distress_classes:
        assert f"`{cls_name}`" in doc_text


def test_goemotions_proxy_labels_marked_as_proxy(label_map):
    """Every GoEmotions mapped emotion MUST have mapping_type: proxy."""
    goemotions = label_map["goemotions"]
    mapped_count = 0
    for emo, spec in goemotions.items():
        if spec.get("target") is not None:
            assert spec.get("mapping_type") == "proxy", f"Emotion {emo} must have mapping_type: proxy"
            mapped_count += 1
        else:
            assert spec.get("mapping_type") in ["unmapped_positive", "unmapped_neutral", "unmapped_epistemic"]
    assert mapped_count > 0


def test_all_mapped_targets_are_valid_classes(contract_distress_classes, label_map):
    """Ensure all mapped targets in GoEmotions and Emotion4 are in the valid DistressClass enum."""
    for dataset_key in ["goemotions", "emotion4"]:
        for emo, spec in label_map[dataset_key].items():
            tgt = spec.get("target")
            if tgt is not None:
                assert tgt in contract_distress_classes, f"Target {tgt} for {emo} not in {contract_distress_classes}"


def test_all_28_goemotions_accounted_for(label_map):
    """Verify all 28 GoEmotions labels are accounted for in label_map.yaml."""
    if GOEMOTIONS_TXT.exists():
        with open(GOEMOTIONS_TXT, "r", encoding="utf-8") as f:
            emotions = [line.strip() for line in f if line.strip()]
        assert len(emotions) == 28
        for emo in emotions:
            assert emo in label_map["goemotions"], f"Missing GoEmotions label: {emo}"


def test_emotion4_classes_accounted_for(label_map):
    """Verify fear, anger, joy, sadness are present in emotion4 mapping."""
    expected = {"fear", "anger", "joy", "sadness"}
    emo4_keys = set(label_map["emotion4"].keys())
    assert expected.issubset(emo4_keys)
    # Check that joy is unmapped (positive)
    assert label_map["emotion4"]["joy"]["target"] is None
    # Check that mapped ones are proxy
    for k in ["fear", "anger", "sadness"]:
        assert label_map["emotion4"][k]["mapping_type"] == "proxy"

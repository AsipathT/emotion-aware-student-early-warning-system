"""
demo/app.py

Streamlit demonstration app for Component 1: Affective State Detection.
Features:
- DistilRoBERTa multi-label prediction on CPU.
- Tuned decision thresholds with horizontal score bars.
- Leave-one-word-out occlusion explainability (no SHAP dependency).
- Side-by-side VADER generic sentiment baseline contrast.
- AffectiveWeeklyVector JSON preview validated against contracts/v1/AffectiveWeeklyVector.json (dry run).
- 'Live from LMS' tab enabled when C1_COMPONENT_KEY is set.
"""

import html
import json
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

# Ensure component root is in sys.path
comp_root = Path(__file__).resolve().parents[1]
if str(comp_root) not in sys.path:
    sys.path.insert(0, str(comp_root))

import jsonschema
import numpy as np
import pandas as pd
import streamlit as st
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from src.evaluation import DEFAULT_CLASSES

# Page configuration
st.set_page_config(
    page_title="C1 Affective State Detection",
    page_icon="🎓",
    layout="wide",
)

EXAMPLE_TEXTS = {
    "Exam Panic": "I have been having panic attacks all morning about the upcoming CS201 final exam. My hands are shaking and I'm terrified I'm going to fail.",
    "Concept Confusion": "I've re-read slide 14 on dynamic programming memoization five times and I still don't understand how the recursive base case terminates.",
    "Academic Helplessness": "No matter how many hours I spend studying this algorithm, nothing works. I give up, I'm just not capable of doing computer science.",
    "Course Frustration": "The autograder has been throwing cryptic runtime errors for 48 hours before the deadline and the teaching assistants haven't replied to any emails.",
    "Motivation Erosion": "I haven't opened the course portal in two weeks. I just can't bring myself to care anymore, I feel completely burned out and numb.",
    "Logistical / Neutral": "Could someone please share the link to today's lecture recording and office hours schedule?",
}


@st.cache_resource
def load_model_and_resources():
    """Loads DistilRoBERTa checkpoint and validation-tuned thresholds on CPU."""
    checkpoint_dir = comp_root / "models" / "checkpoint-best"
    thresholds_path = comp_root / "models" / "thresholds.json"

    if not checkpoint_dir.exists():
        st.error(f"Checkpoint not found at: {checkpoint_dir}")
        return None, None, None

    device = torch.device("cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(checkpoint_dir)).to(device)
    model.eval()

    thresholds = {cls: 0.50 for cls in DEFAULT_CLASSES}
    if thresholds_path.exists():
        with open(thresholds_path, "r", encoding="utf-8") as f:
            thresholds = json.load(f)

    vader_analyzer = SentimentIntensityAnalyzer()

    # Load contract schema
    contract_path = comp_root.parents[0] / "contracts" / "v1" / "AffectiveWeeklyVector.json"
    schema = None
    if contract_path.exists():
        with open(contract_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

    return (model, tokenizer, thresholds), vader_analyzer, schema


def predict_text_scores(
    text: str,
    model: torch.nn.Module,
    tokenizer: AutoTokenizer,
) -> Dict[str, float]:
    """Runs a forward pass on a single text and returns sigmoid probabilities."""
    inputs = tokenizer(
        str(text).strip(),
        max_length=64,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits).squeeze(0).cpu().numpy()

    return {cls: float(probs[i]) for i, cls in enumerate(DEFAULT_CLASSES)}


def compute_word_occlusion(
    text: str,
    target_class: str,
    base_score: float,
    model: torch.nn.Module,
    tokenizer: AutoTokenizer,
) -> List[Tuple[str, float]]:
    """
    Computes leave-one-word-out occlusion importance for target_class.
    Returns list of (word, drop_in_probability).
    """
    words = text.split()
    if len(words) <= 1:
        return [(text.strip(), base_score)]

    # Generate occluded texts
    occluded_texts = []
    for i in range(len(words)):
        occluded = " ".join(words[:i] + words[i + 1 :])
        occluded_texts.append(occluded)

    # Batch tokenize occluded variants
    inputs = tokenizer(
        occluded_texts,
        max_length=64,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits).cpu().numpy()

    c_idx = DEFAULT_CLASSES.index(target_class)
    drops = []
    for i, w in enumerate(words):
        occ_prob = float(probs[i, c_idx])
        drop = max(0.0, base_score - occ_prob)
        drops.append((w, drop))

    return drops


def render_highlighted_text(words_with_drops: List[Tuple[str, float]]) -> str:
    """Renders HTML string with words highlighted proportionally to their occlusion importance."""
    max_drop = max([d for _, d in words_with_drops], default=0.0)
    html_spans = []

    for w, d in words_with_drops:
        w_esc = html.escape(w)
        if max_drop > 0.001 and d > 0.01:
            alpha = min(0.85, (d / max_drop) * 0.75 + 0.15)
            span = f'<span style="background-color: rgba(255, 75, 75, {alpha:.2f}); padding: 2px 4px; border-radius: 4px; font-weight: 600;">{w_esc}</span>'
        else:
            span = f'<span style="color: #333333;">{w_esc}</span>'
        html_spans.append(span)

    return " ".join(html_spans)


def main():
    st.title("Component 1: Student Affective State Detection")
    st.caption("J26-IT-349 AI-Driven Early Warning System — Fine-Tuned DistilRoBERTa on Academic Distress Taxonomy")

    model_bundle, vader_analyzer, contract_schema = load_model_and_resources()
    if not model_bundle:
        st.stop()

    model, tokenizer, thresholds = model_bundle

    # Layout tabs
    tab_interactive, tab_lms = st.tabs(["Interactive Text Analysis", "Live from LMS (Export Feed)"])

    # ── Tab 1: Interactive Analysis ──────────────────────────────────────────
    with tab_interactive:
        col_main, col_vader = st.columns([2.2, 1.0], gap="large")

        with col_main:
            st.subheader("1. Enter Student Message or Select Example")

            # Example selector
            example_cols = st.columns(len(EXAMPLE_TEXTS))
            selected_example = None
            for i, (name, txt) in enumerate(EXAMPLE_TEXTS.items()):
                if example_cols[i].button(name, use_container_width=True):
                    st.session_state["input_text"] = txt

            default_val = st.session_state.get(
                "input_text",
                EXAMPLE_TEXTS["Exam Panic"],
            )
            user_text = st.text_area(
                "Student message text (discussion forum post, chat, or journal):",
                value=default_val,
                height=120,
            )

            if user_text.strip():
                scores = predict_text_scores(user_text, model, tokenizer)

                # Determine passing classes
                predicted_classes = [
                    cls for cls, score in scores.items() if score >= thresholds.get(cls, 0.50)
                ]
                stress_label = predicted_classes[0] if predicted_classes else "none"

                st.markdown("---")
                st.subheader("2. Affective Distress Classification")

                # Status pill
                if stress_label != "none":
                    st.error(f"🚨 **Predicted Distress State:** `{', '.join(predicted_classes)}`")
                else:
                    st.success("✅ **Predicted Distress State:** `none` (No distress threshold exceeded)")

                # Score bars with thresholds
                for cls in DEFAULT_CLASSES:
                    score = scores[cls]
                    t = thresholds.get(cls, 0.50)
                    is_active = score >= t

                    cols = st.columns([1.5, 4.0, 1.2])
                    cols[0].markdown(f"**{cls}**" + (" ⚠️" if is_active else ""))
                    cols[1].progress(min(1.0, score))
                    cols[2].caption(f"Score: **{score:.3f}** (Threshold: {t:.2f})")

                # Occlusion Explainability
                st.markdown("---")
                st.subheader("3. Feature Attribution (Leave-One-Word-Out Occlusion)")
                explain_target = predicted_classes[0] if predicted_classes else max(scores, key=scores.get)
                st.caption(f"Showing words most influential in driving score for: **`{explain_target}`** (Score: {scores[explain_target]:.3f})")

                word_drops = compute_word_occlusion(user_text, explain_target, scores[explain_target], model, tokenizer)
                highlighted_html = render_highlighted_text(word_drops)
                st.markdown(
                    f'<div style="background-color: #f8f9fa; padding: 14px; border-radius: 6px; border-left: 4px solid #ff4b4b; line-height: 1.8;">{highlighted_html}</div>',
                    unsafe_allow_html=True,
                )

                # Top driver tokens
                top_drops = sorted([(w, d) for w, d in word_drops if d > 0.005], key=lambda x: x[1], reverse=True)[:10]
                if top_drops:
                    st.write("**Top Driver Tokens:**")
                    pill_cols = st.columns(min(len(top_drops), 5))
                    for idx, (w, d) in enumerate(top_drops[:5]):
                        pill_cols[idx].metric(label=f"Token: '{w}'", value=f"+{d:.3f}")

                # Weekly Record Preview (Dry Run)
                st.markdown("---")
                st.subheader("4. Weekly Record Preview (`AffectiveWeeklyVector.json`)")
                st.caption("Simulated vector record adhering to contracts/v1/AffectiveWeeklyVector.json (dry run, never POSTed).")

                top_drivers_contract = [
                    {"token_or_marker": w, "weight": round(float(d), 4)} for w, d in top_drops
                ]
                sample_vector = {
                    "pid": "STU_a1b2c3d4",
                    "course_id": "CS101",
                    "week_index": 2,
                    "emotion_scores": {c: round(scores[c], 4) for c in DEFAULT_CLASSES},
                    "stress_label": stress_label,
                    "confidence": round(float(scores[explain_target]), 4),
                    "message_count": 1,
                    "top_drivers": top_drivers_contract,
                }

                # Schema validation check
                schema_valid = False
                validation_msg = ""
                if contract_schema:
                    try:
                        jsonschema.validate(instance=sample_vector, schema=contract_schema)
                        schema_valid = True
                        validation_msg = "Passed validation against contracts/v1/AffectiveWeeklyVector.json"
                    except jsonschema.ValidationError as err:
                        validation_msg = f"Schema validation error: {err.message}"
                else:
                    validation_msg = "Contract schema file not found on disk; validation skipped."

                if schema_valid:
                    st.success(f"✔ **Contract Check:** {validation_msg}")
                else:
                    st.warning(f"ℹ **Contract Check:** {validation_msg}")

                with st.expander("View Generated AffectiveWeeklyVector JSON Payload", expanded=False):
                    st.json(sample_vector)

        # Side panel: VADER baseline comparison
        with col_vader:
            st.subheader("Generic Baseline: VADER")
            st.caption("Rule-based lexicon (no educational/pedagogical context)")

            if user_text.strip():
                v_res = vader_analyzer.polarity_scores(user_text)
                st.metric("Compound Polarity", f"{v_res['compound']:+.3f}")
                st.write(f"- **Positive:** {v_res['pos']:.2f}")
                st.write(f"- **Neutral:**  {v_res['neu']:.2f}")
                st.write(f"- **Negative:** {v_res['neg']:.2f}")

                st.info(
                    """
                    **Key Insight:**  
                    VADER outputs a generic negative score when it sees words like "bad", "panic", or "broken".  
                    However, VADER **cannot distinguish** between:
                    - **Exam Anxiety** (anticipatory panic)
                    - **Conceptual Confusion** (pedagogical blockage)
                    - **Course Frustration** (portal/grading grievance)  

                    Our 5-class fine-tuned model identifies the specific actionable distress type.
                    """
                )

    # ── Tab 2: Live from LMS ─────────────────────────────────────────────────
    with tab_lms:
        st.subheader("Live LMS Message Stream")
        c1_key = os.environ.get("C1_COMPONENT_KEY", "")

        if not c1_key:
            st.warning(
                "🔒 **LMS Live Feed Inactive:** `C1_COMPONENT_KEY` environment variable is not set. "
                "Set `C1_COMPONENT_KEY` to connect directly to `GET /api/v1/export/messages`."
            )
            user_override_key = st.text_input("Or enter C1 Component Key manually to unlock:", type="password")
            if user_override_key:
                c1_key = user_override_key

        if c1_key:
            st.success("🔑 C1 Component Key configured. Ready to fetch live messages.")
            col_cfg1, col_cfg2, col_cfg3 = st.columns([2.0, 1.2, 1.5])
            with col_cfg1:
                lms_url = st.text_input("LMS Base URL:", value=os.environ.get("LMS_BASE_URL", "http://localhost:8000"))
            with col_cfg2:
                fetch_limit = st.selectbox("Max Messages to Fetch:", [20, 50, 100, 250, 500], index=4)
            with col_cfg3:
                search_pid = st.text_input("Filter by Student PID (optional):", placeholder="e.g. STU_7f00e57b")

            if st.button("Fetch Messages from LMS", type="primary"):
                try:
                    from src.lms_client import fetch_messages

                    with st.spinner("Querying LMS export API..."):
                        target_pid = search_pid.strip() if search_pid.strip() else None
                        messages = fetch_messages(limit=fetch_limit, base_url=lms_url, api_key=c1_key, pid=target_pid)

                    if not messages:
                        st.info("No text messages returned from LMS matching criteria.")
                    else:
                        # Sort by timestamp descending (newest posts first)
                        messages_sorted = sorted(
                            messages,
                            key=lambda m: m.get("timestamp") or "",
                            reverse=True,
                        )

                        processed_rows = []
                        distress_count = 0

                        for msg in messages_sorted:
                            clean_text = msg.get("clean_text", "")
                            word_count = len(clean_text.split())
                            is_low_signal = word_count < 3

                            # Predict
                            scores = predict_text_scores(clean_text, model, tokenizer)
                            active_classes = [c for c, s in scores.items() if s >= thresholds.get(c, 0.50)]
                            predicted_label = active_classes[0] if active_classes else "none"
                            if predicted_label != "none":
                                distress_count += 1

                            top_cls = max(scores, key=scores.get)
                            top_val = scores[top_cls]

                            processed_rows.append({
                                "pid": msg.get("pid"),
                                "source_type": msg.get("source_type"),
                                "week_index": msg.get("week_index"),
                                "timestamp": (msg.get("timestamp") or "")[:19].replace("T", " "),
                                "words": word_count,
                                "signal": "LOW SIGNAL (<3 words)" if is_low_signal else "OK",
                                "predicted_label": predicted_label,
                                "top_score_str": f"{top_cls} ({top_val:.2f})",
                                "clean_text": clean_text,
                                "scores": scores,
                            })

                        # Summary metric cards
                        kpi1, kpi2, kpi3 = st.columns(3)
                        kpi1.metric("Total Messages Retrieved", len(processed_rows))
                        kpi2.metric("Distress Alerts Detected", distress_count)
                        kpi3.metric("Neutral / Non-Distress ('none')", len(processed_rows) - distress_count)

                        # Filter controls for dataframe
                        fcol1, fcol2 = st.columns([1.5, 1.5])
                        with fcol1:
                            distress_filter = st.selectbox(
                                "Filter Display Table:",
                                ["All Messages", "Distress Alerts Only", "Neutral ('none') Only"],
                            )
                        with fcol2:
                            source_filter = st.multiselect(
                                "Filter by Source Type:",
                                ["forum", "journal", "chat"],
                                default=["forum", "journal", "chat"],
                            )

                        filtered_display_rows = processed_rows
                        if distress_filter == "Distress Alerts Only":
                            filtered_display_rows = [r for r in filtered_display_rows if r["predicted_label"] != "none"]
                        elif distress_filter == "Neutral ('none') Only":
                            filtered_display_rows = [r for r in filtered_display_rows if r["predicted_label"] == "none"]

                        filtered_display_rows = [r for r in filtered_display_rows if r["source_type"] in source_filter]

                        # Summary table
                        df_display = pd.DataFrame([
                            {
                                "PID": r["pid"],
                                "Source": r["source_type"],
                                "Week": r["week_index"],
                                "Timestamp (UTC)": r["timestamp"],
                                "Signal": r["signal"],
                                "Predicted Label": r["predicted_label"],
                                "Top Score": r["top_score_str"],
                                "Message (Scrubbed)": r["clean_text"],
                            }
                            for r in filtered_display_rows
                        ])
                        st.dataframe(df_display, use_container_width=True)

                        # Per-PID Weekly Record Previews
                        st.markdown("---")
                        st.subheader("Aggregated Weekly Records per Student PID (Dry Run)")
                        pids = sorted(list(set(r["pid"] for r in processed_rows)))

                        for p in pids:
                            student_msgs = [r for r in processed_rows if r["pid"] == p]
                            avg_scores = {}
                            for c in DEFAULT_CLASSES:
                                avg_scores[c] = round(float(np.mean([m["scores"][c] for m in student_msgs])), 4)

                            active = [c for c, s in avg_scores.items() if s >= thresholds.get(c, 0.50)]
                            dominant = active[0] if active else "none"

                            badge = "🚨 " if dominant != "none" else "✅ "
                            pid_vector = {
                                "pid": p,
                                "course_id": "CS101",
                                "week_index": student_msgs[0]["week_index"],
                                "emotion_scores": avg_scores,
                                "stress_label": dominant,
                                "confidence": round(float(max(avg_scores.values())), 4),
                                "message_count": len(student_msgs),
                            }
                            with st.expander(f"{badge}PID: {p} ({len(student_msgs)} messages | Dominant: {dominant})"):
                                st.json(pid_vector)

                except Exception as e:
                    st.error(f"Failed to fetch or process live LMS messages: {e}")


if __name__ == "__main__":
    main()

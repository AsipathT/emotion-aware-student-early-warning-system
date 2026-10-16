"""Short AI-generated explanation of a recommendation, using the OpenAI API.

Only the model inputs and outputs are sent. Names and IDs are not.
"""
import logging
from datetime import datetime, timezone

from . import config
from .reference import CONDITIONS, INTERVENTIONS

log = logging.getLogger("c4")

class ExplanationUnavailable(Exception):
    """OpenAI is not configured or the request failed. The message is safe to show to users."""


SYSTEM_PROMPT = (
    "You help school counsellors understand recommendations from a machine-learning model that suggests "
    "student support interventions. Write a short explanation of 3-4 sentences and under 110 words, in plain, "
    "supportive language. Explain why the top recommendation fits this student's inputs, say briefly when one "
    "of the other options might be preferred, and if past recommendations are listed, mention any pattern or "
    "change. Use only the information provided. Do not invent statistics, outcomes or personal details, and do "
    "not diagnose. The model was trained on synthetic prototype data, so describe the percentages as model "
    "suitability scores, not proven effectiveness. No headings or bullet points."
)


def _describe(assessment: dict) -> str:
    i = assessment["inputs"]
    c3 = i["c3"]
    return (
        f"C1 condition: {i['c1_condition']}; C2 trajectory: {i['c2_trajectory']}; "
        f"dropout risk score {i['risk_probability']:.2f} ({i['risk_tier']} risk); "
        f"C3 causal strengths: Affective {c3['affective']:.2f}, Behavioural {c3['behavioural']:.2f}, "
        f"Academic {c3['academic']:.2f} (strongest: {i['c3_dominant']})"
    )


def build_user_prompt(student: dict, assessment: dict, past: list[dict]) -> str:
    inputs = assessment["inputs"]
    lines = [
        f"Assessment date: {assessment['created_at'][:10]}",
        f"Inputs: {_describe(assessment)}",
        f"About the condition: {CONDITIONS.get(inputs['c1_condition'], '')}",
        "",
        "Model suitability scores (top 3):",
    ]
    for rank, option in enumerate(assessment["recommendations"], start=1):
        name = option["intervention"]
        lines.append(f"{rank}. {name} - {option['suitability']:.0%} ({INTERVENTIONS.get(name, '')})")
    lines += ["", "Past recommendations for this student (oldest first):"]
    if past:
        for old in past:
            top = old["recommendations"][0]
            lines.append(f"- {old['created_at'][:10]}: {top['intervention']} ({top['suitability']:.0%}); {_describe(old)}")
    else:
        lines.append("- None")
    return "\n".join(lines)


def _friendly_error(exc) -> str:
    import openai

    if isinstance(exc, openai.AuthenticationError):
        return "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env."
    if isinstance(exc, openai.NotFoundError):
        return f"OpenAI model '{config.OPENAI_MODEL}' was not found. Check OPENAI_MODEL in backend/.env."
    if isinstance(exc, openai.RateLimitError):
        return "OpenAI rate limit or quota reached. Please try again later."
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return "Could not reach OpenAI. Check the internet connection and try again."
    return "The OpenAI request failed. Please try again."


def generate_explanation(student: dict, assessment: dict, past: list[dict]) -> dict:
    if not config.OPENAI_API_KEY:
        raise ExplanationUnavailable(
            "AI explanation is not available: set OPENAI_API_KEY in backend/.env and restart the backend.")

    import openai

    client = openai.OpenAI(api_key=config.OPENAI_API_KEY, timeout=config.OPENAI_TIMEOUT_SECONDS, max_retries=1)
    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(student, assessment, past)},
            ],
        )
    except openai.OpenAIError as exc:
        log.warning("OpenAI request failed: %r", exc)
        raise ExplanationUnavailable(_friendly_error(exc)) from exc

    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise ExplanationUnavailable("OpenAI returned an empty explanation. Please try again.")
    return {
        "text": text,
        "ai_generated": True,
        "provider": "OpenAI",
        "model": response.model or config.OPENAI_MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "past_recommendations_used": len(past),
    }

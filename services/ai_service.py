import os

import requests
from config import get_settings

settings = get_settings()

MODEL_ID = settings.hf_model_id
CHAT_API_URL = os.getenv("HF_CHAT_API_URL", "https://router.huggingface.co/v1/chat/completions")
HF_API_KEY = settings.hf_api_key
FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "HF_FALLBACK_MODELS",
        "meta-llama/Llama-3.1-8B-Instruct,Qwen/Qwen2.5-7B-Instruct,microsoft/Phi-3-mini-4k-instruct",
    ).split(",")
    if model.strip()
]

headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}
SYSTEM_PROMPT = (
    "You are a helpful study assistant for college students. "
    "Give complete answers without cutting off mid-sentence. "
    "Format the reply cleanly using short markdown section headings, bold key terms, "
    "bullet points when helpful, and fenced code blocks for code."
)
MAX_COMPLETION_TOKENS = 900
MAX_CONTINUATIONS = 2


def _stringify_error(error_value) -> str:
    if isinstance(error_value, str):
        return error_value
    if isinstance(error_value, dict):
        for key in ("message", "error", "detail", "details", "error_description"):
            value = error_value.get(key)
            if value:
                return _stringify_error(value)
        return str(error_value)
    if isinstance(error_value, list):
        parts = [_stringify_error(item) for item in error_value]
        return "; ".join(part for part in parts if part)
    return str(error_value or "")


def _normalize_error_message(error_text, status_code: int | None = None) -> str:
    normalized_text = _stringify_error(error_text).strip()
    lowered = normalized_text.lower()

    if status_code in {401, 403} or "expired" in lowered or "access token" in lowered or "unauthorized" in lowered:
        return (
            "Your Hugging Face API token is invalid or expired. "
            "Update HF_API_KEY in .env with a new token from your Hugging Face account."
        )

    if "model" in lowered and ("not found" in lowered or "enabled" in lowered or "does not exist" in lowered):
        return (
            "The selected Hugging Face model is not available for this token. "
            "Set HF_MODEL_ID in .env to a model enabled in your Hugging Face account."
        )

    return normalized_text or "Unknown AI service error."


def _extract_error(response):
    try:
        data = response.json()
    except ValueError:
        raw_error = f"AI service error ({response.status_code}): {response.text[:200]}"
        return _normalize_error_message(raw_error, response.status_code), None
    if isinstance(data, dict):
        raw_error = data.get("error", f"AI service error ({response.status_code}).")
        return _normalize_error_message(raw_error, response.status_code), data
    return _normalize_error_message(f"AI service error ({response.status_code}).", response.status_code), data


def _parse_inference_response(data):
    if isinstance(data, list):
        item = data[0] if data else {}
        return item.get("generated_text") or item.get("summary_text") or "No response"
    return data.get("error", str(data)) if isinstance(data, dict) else str(data)


def _ask_chat_route(messages, model_id: str):
    response = requests.post(
        CHAT_API_URL,
        headers={**headers, "Content-Type": "application/json"},
        json={
            "model": model_id,
            "messages": messages,
            "max_tokens": MAX_COMPLETION_TOKENS,
            "temperature": 0.7,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        error_text, _ = _extract_error(response)
        return None, error_text

    try:
        data = response.json()
    except ValueError:
        return None, f"AI service error ({response.status_code}): {response.text[:200]}"

    choices = data.get("choices", []) if isinstance(data, dict) else []
    if choices:
        choice = choices[0]
        msg = choice.get("message", {})
        content = msg.get("content")
        if content:
            return {
                "content": content,
                "finish_reason": choice.get("finish_reason"),
            }, None
    return {"content": str(data), "finish_reason": None}, None


def ask_ai(question: str):
    if not HF_API_KEY:
        return (
            "AI service is not configured. Set HF_API_KEY "
            "(or HUGGINGFACE_API_KEY) in your deployment environment variables."
        )

    models_to_try = [MODEL_ID] + [m for m in FALLBACK_MODELS if m != MODEL_ID]
    last_error = "Unknown AI service error."
    for model_id in models_to_try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        output, error = _ask_chat_route(messages, model_id)
        if output:
            answer_parts = [output["content"].strip()]
            finish_reason = output.get("finish_reason")

            for _ in range(MAX_CONTINUATIONS):
                if finish_reason not in {"length", "max_tokens"}:
                    break
                messages.extend(
                    [
                        {"role": "assistant", "content": "\n\n".join(part for part in answer_parts if part)},
                        {
                            "role": "user",
                            "content": (
                                "Continue from exactly where you stopped. "
                                "Do not repeat earlier content. Finish the remaining answer."
                            ),
                        },
                    ]
                )
                continuation, continuation_error = _ask_chat_route(messages, model_id)
                if continuation_error or not continuation:
                    break
                answer_parts.append(continuation["content"].strip())
                finish_reason = continuation.get("finish_reason")

            return "\n\n".join(part for part in answer_parts if part)
        if error:
            last_error = error
            if "token is invalid or expired" in error.lower():
                return error

    if "model is not available" in last_error.lower():
        return last_error

    return last_error

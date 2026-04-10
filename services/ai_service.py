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


def _normalize_error_message(error_text: str, status_code: int | None = None) -> str:
    lowered = (error_text or "").lower()

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

    return error_text or "Unknown AI service error."


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


def _ask_chat_route(question: str, model_id: str):
    response = requests.post(
        CHAT_API_URL,
        headers={**headers, "Content-Type": "application/json"},
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": question}],
            "max_tokens": 300,
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
        msg = choices[0].get("message", {})
        content = msg.get("content")
        if content:
            return content, None
    return str(data), None


def ask_ai(question: str):
    if not HF_API_KEY:
        return (
            "AI service is not configured. Set HF_API_KEY "
            "(or HUGGINGFACE_API_KEY) in your deployment environment variables."
        )

    models_to_try = [MODEL_ID] + [m for m in FALLBACK_MODELS if m != MODEL_ID]
    last_error = "Unknown AI service error."
    for model_id in models_to_try:
        output, error = _ask_chat_route(question, model_id)
        if output:
            return output
        if error:
            last_error = error
            if "token is invalid or expired" in error.lower():
                return error

    if "model is not available" in last_error.lower():
        return last_error

    return last_error

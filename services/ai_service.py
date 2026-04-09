import requests

API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"

headers = {
    "Authorization": "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"
}

def ask_ai(question: str):
    response = requests.post(
        API_URL,
        headers=headers,
        json={"inputs": question}
    )

    data = response.json()

    # Handle HuggingFace response safely
    if isinstance(data, list):
        return data[0].get("generated_text", "No response")
    
    return str(data)
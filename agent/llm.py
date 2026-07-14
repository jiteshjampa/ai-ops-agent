"""
Thin wrapper around the LLM provider so the rest of the agent doesn't
care which model is behind it. Uses Groq (Llama 3) by default since it's
free-tier, fast, and already on your stack (same as your RAG project).

Swap MODEL_NAME or the provider block below if you'd rather use Gemini.
"""

import os
import json
from groq import Groq

MODEL_NAME = "llama-3.3-70b-versatile"

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
                "and set it as an environment variable or in a .env file."
            )
        _client = Groq(api_key=api_key)
    return _client


def chat(system_prompt: str, user_prompt: str, json_mode: bool = False, temperature: float = 0.2) -> str:
    """Single-turn call to the LLM. Returns raw text (or a JSON string if json_mode=True)."""
    client = get_client()
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    return response.choices[0].message.content


def chat_json(system_prompt: str, user_prompt: str) -> dict:
    """Same as chat() but parses the result as JSON, with a safety fallback."""
    raw = chat(system_prompt, user_prompt, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # strip markdown fences if the model added them anyway
        cleaned = raw.strip().strip("`").replace("json\n", "", 1)
        return json.loads(cleaned)

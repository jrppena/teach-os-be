"""Provider-agnostic AI generation over httpx.

Dispatches a single JSON-producing chat request to whichever provider is active
(Gemini or Grok) and returns the parsed JSON object. No provider SDKs are used —
only ``httpx`` (the project's HTTP client) — so the two REST shapes are handled
here explicitly:

- Gemini: ``POST {base}/models/{model}:generateContent`` with an ``x-goog-api-key``
  header, a ``system_instruction`` + ``contents`` body, and
  ``generationConfig.responseMimeType="application/json"``. The JSON is read from
  ``candidates[0].content.parts[*].text``. (The schema is enforced via the prompt;
  Gemini's responseSchema dialect is intentionally not used.)
- Grok: OpenAI-compatible ``POST {base}/chat/completions`` with a Bearer header and
  ``response_format={"type":"json_schema", ...}`` carrying the canonical schema.
  The JSON is read from ``choices[0].message.content``.

Callers always re-validate the returned dict against the Pydantic
``GeneratedLessonPlan`` model — that, not the per-provider structured-output
feature, is the real shape guarantee.
"""

import json

import httpx

from src.lesson_plans.config import settings
from src.lesson_plans.exceptions import ProviderError, ProviderResponseError
from src.settings.schemas import ProviderId


def _parse_json_payload(text: str) -> dict:
    """Parse a model text payload into a dict, tolerating stray code fences.

    Inputs: the raw text the provider returned (expected to be a JSON object).
    Outputs: the parsed ``dict``.
    Side effects: raises ``ProviderResponseError`` when the text is empty or not a
    JSON object.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Defensive: strip a ```json ... ``` fence if a model adds one.
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if not cleaned:
        raise ProviderResponseError("The AI provider returned an empty response.")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError(
            "The AI provider did not return valid JSON. Please try again."
        ) from exc
    if not isinstance(data, dict):
        raise ProviderResponseError("The AI provider returned JSON that was not an object.")
    return data


async def _generate_gemini(
    client: httpx.AsyncClient,
    api_key: str,
    system_prompt: str,
    user_message: str,
) -> dict:
    """Call Gemini ``generateContent`` and return the parsed JSON object."""
    url = f"{settings.GEMINI_BASE_URL}/models/{settings.GEMINI_MODEL}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": settings.MAX_OUTPUT_TOKENS,
        },
    }
    response = await client.post(
        url,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
    )
    _raise_for_status(response)
    body = response.json()
    try:
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderResponseError(
            "Gemini returned no content (the request may have been blocked)."
        ) from exc
    return _parse_json_payload(text)


async def _generate_grok(
    client: httpx.AsyncClient,
    api_key: str,
    system_prompt: str,
    user_message: str,
    schema: dict,
) -> dict:
    """Call Grok chat completions and return the parsed JSON object."""
    url = f"{settings.GROK_BASE_URL}/chat/completions"
    payload = {
        "model": settings.GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "lesson_plan", "schema": schema, "strict": True},
        },
        "max_tokens": settings.MAX_OUTPUT_TOKENS,
    }
    response = await client.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    _raise_for_status(response)
    body = response.json()
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderResponseError("Grok returned no message content.") from exc
    return _parse_json_payload(text or "")


def _raise_for_status(response: httpx.Response) -> None:
    """Raise ``ProviderError`` with a trimmed body on a non-2xx provider response."""
    if response.is_success:
        return
    raise ProviderError(
        f"The AI provider responded with HTTP {response.status_code}. "
        "Check that the API key is valid and the selected model is available."
    )


async def generate_json(
    provider: ProviderId,
    api_key: str,
    system_prompt: str,
    user_message: str,
    schema: dict,
) -> dict:
    """Generate a JSON object from the given provider.

    Args:
        provider: The active provider (``gemini`` or ``grok``).
        api_key: The user's decrypted API key for that provider.
        system_prompt: The ILAW system prompt.
        user_message: The rendered wizard inputs.
        schema: Canonical JSON Schema (used by Grok's structured-output feature;
            ignored by Gemini, which relies on the prompt + JSON mime type).

    Returns:
        The parsed JSON object (still unvalidated against the domain schema).

    Side effects:
        One HTTP request to the provider. Raises ``ProviderError`` on transport/
        HTTP failure and ``ProviderResponseError`` on a missing/unparseable payload.
    """
    async with httpx.AsyncClient(timeout=settings.TIMEOUT_SECONDS) as client:
        try:
            if provider == ProviderId.GEMINI:
                return await _generate_gemini(client, api_key, system_prompt, user_message)
            return await _generate_grok(client, api_key, system_prompt, user_message, schema)
        except httpx.HTTPError as exc:
            raise ProviderError(
                "Could not reach the AI provider (network error or timeout). Please try again."
            ) from exc

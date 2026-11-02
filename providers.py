"""Text drafting only. Provider keys stay in the server process."""
import http.client
import json
import os
import re
from urllib.parse import quote


# Explicit models let the operator choose an available model and its cost.
PROVIDERS = {
    "openai": ("OpenAI", "OPENAI_API_KEY", "OFFICE_OPENAI_MODEL"),
    "anthropic": ("Claude", "ANTHROPIC_API_KEY", "OFFICE_ANTHROPIC_MODEL"),
    "gemini": ("Gemini", "GEMINI_API_KEY", "OFFICE_GEMINI_MODEL"),
    "meta": ("Meta Muse", "MODEL_API_KEY", "OFFICE_META_MODEL"),
}


class ProviderError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def allowed_models(provider):
    """Operator-owned IDs only; the first valid entry is the default."""
    _, _, model_var = PROVIDERS[provider]
    entries = [os.environ.get(model_var, ""), *os.environ.get(model_var + "S", "").split(",")]
    models = []
    for entry in entries:
        model = entry.strip()
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", model) and model not in models:
            models.append(model)
        if len(models) == 64:
            break
    return models


def resolve_route(provider, model=None):
    """Validate a saved/requested route without requiring a credential."""
    if not isinstance(provider, str) or provider not in ("demo", *PROVIDERS):
        raise ProviderError("Unknown drafting provider.", 400)
    if model is not None and not isinstance(model, str):
        raise ProviderError("Model must be an allowed model ID.", 400)
    if provider == "demo":
        if model:
            raise ProviderError("Local demo does not use a model ID.", 400)
        return {"provider": "demo", "model": ""}
    models = allowed_models(provider)
    if not models:
        raise ProviderError("Configure an allowed model for this provider on the local server.", 409)
    if model and model not in models:
        raise ProviderError("That model is not in the provider's local allowlist.", 400)
    return {"provider": provider, "model": model or models[0]}


def list_providers():
    options = [{"id": "demo", "label": "Local demo", "configured": True, "models": []}]
    for key, (label, secret_var, _) in PROVIDERS.items():
        models = allowed_models(key)
        configured = bool(os.environ.get(secret_var) and models)
        options.append({"id": key, "label": label, "configured": configured, "models": models})
    return options


def _post(host, path, headers, payload):
    """One HTTPS request to a fixed provider host. Never follow redirects or relay raw errors."""
    conn = http.client.HTTPSConnection(host, timeout=45)
    try:
        conn.request("POST", path, json.dumps(payload).encode(), {
            "Content-Type": "application/json", **headers,
        })
        response = conn.getresponse()
        if response.status != 200:
            raise ProviderError(f"The provider returned HTTP {response.status}. Check its model, credentials and usage limits.")
        raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ProviderError("The provider response exceeded the drafting limit.")
        return json.loads(raw)
    except (OSError, http.client.HTTPException, UnicodeError, ValueError) as exc:
        raise ProviderError("The provider could not return a readable response.") from exc
    finally:
        conn.close()


def generate_draft(provider, instruction, brief, model=None):
    route = resolve_route(provider, model)
    model = route["model"]
    if provider == "demo":
        return (f"Simulated draft for owner review\n\nRequested work: {brief}\n\n"
                "Suggested next step: review the request, identify missing details, "
                "and approve or decline this draft in the boardroom.")
    label, secret_var, _ = PROVIDERS[provider]
    key = os.environ.get(secret_var)
    if not key:
        raise ProviderError(f"Configure {label} on the local server before drafting.", 409)
    system = ("Prepare a concise draft for the owner to review. Do not claim you sent, "
              "published, filed, or carried out any action. Flag missing facts.\n\n"
              f"Office instructions:\n{instruction}")
    try:
        if provider == "openai":
            result = _post("api.openai.com", "/v1/responses", {"Authorization": f"Bearer {key}"}, {
                "model": model, "input": brief, "instructions": system,
                "store": False, "max_output_tokens": 1024,
            })
            parts = [p["text"] for item in result["output"] if item.get("type") == "message"
                     for p in item["content"] if p.get("type") == "output_text"]
        elif provider == "anthropic":
            result = _post("api.anthropic.com", "/v1/messages", {
                "x-api-key": key, "anthropic-version": "2023-06-01",
            }, {"model": model, "max_tokens": 1024, "system": system,
                "messages": [{"role": "user", "content": brief}]})
            parts = [p["text"] for p in result["content"] if p.get("type") == "text"]
        elif provider == "meta":
            result = _post("api.meta.ai", "/v1/chat/completions", {"Authorization": f"Bearer {key}"}, {
                "model": model, "max_completion_tokens": 1024,
                "messages": [{"role": "developer", "content": system}, {"role": "user", "content": brief}],
            })
            parts = [result["choices"][0]["message"]["content"]]
        else:
            path = f"/v1beta/models/{quote(model, safe='')}:generateContent"
            result = _post("generativelanguage.googleapis.com", path, {"x-goog-api-key": key}, {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": brief}]}],
                "generationConfig": {"maxOutputTokens": 1024},
            })
            parts = [p["text"] for p in result["candidates"][0]["content"]["parts"]
                     if "text" in p and not p.get("thought")]
        answer = "\n".join(parts).strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError(f"{label} did not return draft text.") from exc
    if not answer:
        raise ProviderError(f"{label} returned no draft text.")
    return answer

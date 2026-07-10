"""
Shared Claude API helper — single source of truth for the model ID,
client construction, error handling, and structured (schema-enforced)
responses.

Instead of asking Claude to "respond with only JSON" and regex-stripping
markdown fences, every call forces a tool invocation with a JSON schema.
The API validates the shape, so parse failures effectively disappear.
"""
import json
import os

import anthropic


# Override with the RESUMEAGENT_MODEL env var if your account/gateway
# needs a different model ID.
DEFAULT_MODEL = os.environ.get("RESUMEAGENT_MODEL", "claude-sonnet-4-5")


def describe_api_error(exc, model: str, base_url: str | None) -> str:
    """
    Build a user-facing message for an API failure.

    Deliberately does NOT include the prompt: the prompt contains the full
    resume (name, phone, email), and error text ends up in the UI and logs.

    `exc` only needs `.status_code` and `.body` attributes.
    """
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    endpoint = base_url or "api.anthropic.com"

    if isinstance(body, str):
        body_text = body
    elif body:
        try:
            body_text = json.dumps(body)
        except (TypeError, ValueError):
            body_text = str(body)
    else:
        body_text = ""

    lines = [f"Claude API error (HTTP {status}) from {endpoint} using model '{model}'."]

    # Anthropic's API always returns JSON error bodies; a plain-text body
    # means a proxy/firewall in front of the API rejected the request.
    if status == 403 and isinstance(body, str):
        lines.append(
            "The block came from a proxy or firewall in front of the API, "
            "not from Anthropic. Use a personal Anthropic API key with the "
            "Base URL left blank in Settings."
        )
    elif status == 401:
        lines.append("Authentication failed — check the API key in Settings.")
    elif status == 404:
        lines.append(
            f"Model '{model}' was not found on {endpoint} — set a supported "
            "model ID via the RESUMEAGENT_MODEL environment variable."
        )
    elif status == 429:
        lines.append("Rate limited — wait a minute and try again.")
    elif status is not None and status >= 500:
        lines.append("Server error on the API side — retry in a bit.")

    if body_text:
        lines.append(f"Details: {body_text[:300]}")

    return "\n".join(lines)


def call_claude_structured(
    task: str,
    system: str,
    user_msg: str,
    schema: dict,
    api_key: str,
    max_tokens: int,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> dict:
    """
    Send one message to Claude and force a schema-shaped reply via tool use.

    Returns the tool input dict (already schema-validated by the API).
    Raises RuntimeError with a user-facing, prompt-free message on failure.
    """
    model = model or DEFAULT_MODEL
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**client_kwargs)

    request = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
        "tools": [
            {
                "name": "emit_result",
                "description": f"Record the final {task} result.",
                "input_schema": schema,
            }
        ],
        "tool_choice": {"type": "tool", "name": "emit_result"},
    }
    if temperature is not None:
        request["temperature"] = temperature

    try:
        response = client.messages.create(**request)
    except anthropic.APIStatusError as exc:
        raise RuntimeError(
            f"Claude API error during {task}:\n"
            + describe_api_error(exc, model, base_url)
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(
            f"Could not reach {base_url or 'api.anthropic.com'} during {task}. "
            f"Check your network and the Base URL in Settings. ({exc})"
        ) from exc

    block = next((b for b in response.content if b.type == "tool_use"), None)
    if block is None:
        raise RuntimeError(f"Claude returned no structured content during {task}.")

    return block.input

import os
import logging
import requests
import asyncio
from typing import Optional, Dict, Any

LOGGER = logging.getLogger(__name__)
# Configure these via environment variables (never hardcode keys)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_ENDPOINT = os.getenv("OPENROUTER_ENDPOINT", "https://api.openrouter.ai/v1/chat/completions")
# Optional: notification webhook or admin user id to alert on billing issues
ADMIN_ALERT_WEBHOOK = os.getenv("ADMIN_ALERT_WEBHOOK")  # e.g., a Discord webhook URL

class InsufficientCreditsError(RuntimeError):
    pass

class AIProviderError(RuntimeError):
    pass

def redact_key(key: Optional[str]) -> str:
    if not key:
        return "<empty>"
    if len(key) <= 10:
        return key[0:3] + "..." + key[-3:]
    return key[:6] + "..." + key[-4:]

def call_openrouter_api(api_key: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """
    Calls the OpenRouter-like endpoint and handles common error cases.
    Returns parsed JSON for success, raises InsufficientCreditsError on 402,
    raises AIProviderError on other provider failures.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    LOGGER.debug("Sending AI request with API key: %s", redact_key(api_key))

    try:
        resp = requests.post(OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        LOGGER.exception("Network error calling AI provider")
        raise AIProviderError("Network error contacting AI provider") from e

    LOGGER.debug("Response status code: %s", resp.status_code)

    # Try to parse JSON body (if any) for diagnostics without leaking secrets
    try:
        body = resp.json()
    except ValueError:
        body = {"text": resp.text}

    if resp.status_code == 200:
        return body
    if resp.status_code == 402:
        # Insufficient credits — handle specially
        LOGGER.error("AI provider returned 402 Insufficient credits for key: %s; body=%s",
                     redact_key(api_key), body)
        raise InsufficientCreditsError("AI provider: insufficient credits")
    # Handle common client/server errors gracefully
    LOGGER.error("AI provider returned non-200 status: %s, body=%s", resp.status_code, body)
    raise AIProviderError(f"AI provider returned status {resp.status_code}")

# A simple fallback that keeps the bot usable when AI is unavailable.
# Replace or extend with a different provider or canned responses.
def fallback_reply(user_message: str) -> str:
    # For safety, return a friendly canned response instead of exposing internal errors.
    # You can expand this to use a smaller local model or cached responses.
    return ("Sorry, the AI is temporarily unavailable (billing or network issue). "
            "You can try again in a few minutes or ask for help from a human moderator.")

# Example integration helper for Discord bots (discord.py). Adapt to your bot's structure.
# This function is library-agnostic in the sense it just returns the reply text.
def handle_user_ai_request(user_message: str) -> str:
    """
    Synchronous wrapper for simplicity. If your bot is async, call this inside run_in_executor
    or adapt to async/await.
    """
    api_key = OPENROUTER_API_KEY
    if not api_key:
        LOGGER.error("No OpenRouter API key configured (OPENROUTER_API_KEY)")
        return ("AI is not configured. Please contact the bot administrators.")

    # Build a payload appropriate for your provider. Adjust fields as needed.
    payload = {
        "model": "gpt-4o-mini",  # adjust to your provider/model
        "messages": [{"role": "user", "content": user_message}],
        "max_tokens": 800
    }

    try:
        result = call_openrouter_api(api_key, payload)
        # adapt to actual response schema; here's a typical shape for chat completions:
        if isinstance(result, dict):
            # try multiple fallbacks to extract text
            if "choices" in result and isinstance(result["choices"], list) and len(result["choices"]) > 0:
                text = result["choices"][0].get("message", {}).get("content")
                if text:
                    return text
            # provider might return a top-level 'output' or 'text'
            if "output" in result:
                return result["output"]
            if "text" in result:
                return result["text"]
        # If structure unexpected, guard with fallback
        LOGGER.error("Unexpected AI response structure: %s", {k: (type(v).__name__) for k, v in (result or {}).items()})
        return fallback_reply(user_message)

    except InsufficientCreditsError:
        # Optionally notify admins asynchronously
        LOGGER.warning("Insufficient credits for AI provider; notifying admin if configured.")
        if ADMIN_ALERT_WEBHOOK:
            # Don't block: fire and forget
            try:
                requests.post(ADMIN_ALERT_WEBHOOK, json={
                    "content": ":warning: AI provider returned insufficient credits. Please top up or replace the key."
                }, timeout=5)
            except Exception:
                LOGGER.exception("Failed to send admin alert webhook")
        # Return a friendly message to user
        return ("The AI service is currently unavailable due to billing (insufficient credits). "
                "Please try again later or contact the server admins.")
    except AIProviderError:
        LOGGER.exception("AI provider error")
        return fallback_reply(user_message)
    except Exception:
        LOGGER.exception("Unexpected error while calling AI provider")
        return fallback_reply(user_message)

# Minimal async health-check you can schedule on a loop
async def ai_provider_health_check(interval_seconds: int = 300):
    """
    Periodically does a lightweight request to detect 402 and alert admins.
    Run this as a background task in your bot's event loop.
    """
    while True:
        try:
            # A very small test payload; ensure provider supports such calls (be mindful of cost).
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }
            try:
                call_openrouter_api(OPENROUTER_API_KEY, payload, timeout=10)
                LOGGER.debug("AI provider health-check OK")
            except InsufficientCreditsError:
                LOGGER.error("AI provider health-check failed: insufficient credits")
                if ADMIN_ALERT_WEBHOOK:
                    try:
                        requests.post(ADMIN_ALERT_WEBHOOK, json={
                            "content": ":rotating_light: AI provider returned 402 Insufficient credits — please top up."
                        }, timeout=5)
                    except Exception:
                        LOGGER.exception("Failed to send admin alert webhook")
            except AIProviderError:
                LOGGER.error("AI provider health-check returned an error")
        except Exception:
            LOGGER.exception("Unhandled error in ai_provider_health_check loop")
        await asyncio.sleep(interval_seconds)
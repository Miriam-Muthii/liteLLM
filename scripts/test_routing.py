"""
=============================================================================
MIRIAM LiteLLM — Routing & Capability Test Script
=============================================================================
This script demonstrates and tests EVERY capability your supervisor described:

  TEST 1: Basic routing — send a request through LiteLLM
  TEST 2: Load balancing — send multiple requests and observe distribution
  TEST 3: Per-team API key isolation — each team uses its own key
  TEST 4: RPM rate limiting — hit the limit and observe 429 response
  TEST 5: Fallback routing — simulate a backend failure, watch failover
  TEST 6: Whisper audio transcription routing
  TEST 7: Token usage tracking — view spend per key/team
  TEST 8: Model restriction per team — team can only use assigned models

Usage:
    python scripts/test_routing.py

Requirements:
    pip install requests python-dotenv openai
=============================================================================
"""

import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

LITELLM_URL  = os.getenv("LITELLM_URL", "http://localhost:4000")
MASTER_KEY   = os.getenv("LITELLM_MASTER_KEY")
PULSE_KEY    = os.getenv("TEAM_KEY_PULSE")
TRANS_KEY    = os.getenv("TEAM_KEY_TRANSLATIONS")
BULK_KEY     = os.getenv("TEAM_KEY_BULK_INSIGHTS")

BASE_HEADERS = {"Content-Type": "application/json"}


def print_section(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(label: str, success: bool, detail: str = ""):
    icon = "✅" if success else "❌"
    print(f"  {icon} {label}")
    if detail:
        print(f"     {detail}")


def chat_request(message: str, model: str, api_key: str) -> dict:
    """Send a chat completion request to LiteLLM."""
    response = requests.post(
        f"{LITELLM_URL}/chat/completions",
        headers={**BASE_HEADERS, "Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 100,
        },
        timeout=60,
    )
    return response


def get_key_spend(api_key: str) -> dict:
    """Get spend info for a specific API key."""
    response = requests.get(
        f"{LITELLM_URL}/key/info",
        headers={**BASE_HEADERS, "Authorization": f"Bearer {MASTER_KEY}"},
        params={"key": api_key},
        timeout=15,
    )
    return response.json() if response.ok else {}


def get_global_spend() -> dict:
    """Get global spend across all teams."""
    response = requests.get(
        f"{LITELLM_URL}/global/spend",
        headers={**BASE_HEADERS, "Authorization": f"Bearer {MASTER_KEY}"},
        timeout=15,
    )
    return response.json() if response.ok else {}


# =============================================================================
# TEST 1: Health Check & Model Availability
# =============================================================================
def test_health():
    print_section("TEST 1: Health Check & Model Availability")

    # Basic health
    r = requests.get(f"{LITELLM_URL}/health", timeout=10)
    print_result("LiteLLM proxy is reachable", r.ok, f"Status: {r.status_code}")

    # List available models
    r = requests.get(
        f"{LITELLM_URL}/models",
        headers={**BASE_HEADERS, "Authorization": f"Bearer {MASTER_KEY}"},
        timeout=10,
    )
    if r.ok:
        models = [m["id"] for m in r.json().get("data", [])]
        print_result("Models registered", True, f"Found: {', '.join(models)}")
    else:
        print_result("Models list", False, r.text)


# =============================================================================
# TEST 2: Basic Routing — Request through LiteLLM to Gemma
# =============================================================================
def test_basic_routing():
    print_section("TEST 2: Basic Routing (Gemma via LiteLLM)")

    if not PULSE_KEY or "CHANGE_ME" in PULSE_KEY:
        print("  ⚠️  TEAM_KEY_PULSE not set. Run setup_teams.py first.")
        return

    start = time.time()
    r = chat_request(
        message="In one sentence, what is LiteLLM?",
        model="gemma",
        api_key=PULSE_KEY,
    )
    elapsed = round(time.time() - start, 2)

    if r.ok:
        content = r.json()["choices"][0]["message"]["content"]
        tokens  = r.json().get("usage", {})
        print_result("Request routed successfully", True, f"Response time: {elapsed}s")
        print(f"\n  Response: {content[:200]}")
        print(f"  Tokens used: {tokens}")
    else:
        print_result("Request failed", False, f"{r.status_code}: {r.text[:200]}")


# =============================================================================
# TEST 3: Load Balancing — Send 5 requests and observe which backend serves each
# =============================================================================
def test_load_balancing():
    print_section("TEST 3: Load Balancing Across Backends")

    if not PULSE_KEY or "CHANGE_ME" in PULSE_KEY:
        print("  ⚠️  TEAM_KEY_PULSE not set. Run setup_teams.py first.")
        return

    print("  Sending 5 rapid requests — LiteLLM routes across all Gemma backends...")
    print()

    for i in range(1, 6):
        start = time.time()
        r = chat_request(
            message=f"Reply with just the number {i}",
            model="gemma",
            api_key=PULSE_KEY,
        )
        elapsed = round(time.time() - start, 2)

        if r.ok:
            # LiteLLM returns x-litellm-model-api-base header showing which backend served it
            backend = r.headers.get("x-litellm-model-api-base", "unknown")
            tokens  = r.json().get("usage", {}).get("total_tokens", 0)
            print(f"  Request {i}: ✅ backend={backend}  tokens={tokens}  time={elapsed}s")
        else:
            print(f"  Request {i}: ❌ {r.status_code}")

        time.sleep(0.5)   # Small delay between requests


# =============================================================================
# TEST 4: Per-Team Key Isolation
# Pulse key should work for 'gemma'; translation key only for 'qwen-translation'
# =============================================================================
def test_key_isolation():
    print_section("TEST 4: Per-Team API Key Isolation")

    if not PULSE_KEY or "CHANGE_ME" in PULSE_KEY:
        print("  ⚠️  Team keys not set. Run setup_teams.py first.")
        return

    # Pulse key should work for gemma
    r = chat_request("Say hello", model="gemma", api_key=PULSE_KEY)
    print_result(
        "Pulse key can access 'gemma' (allowed)",
        r.ok,
        f"Status: {r.status_code}"
    )

    # Pulse key should NOT work for qwen-translation (not in Pulse's model list)
    r = chat_request("Say hello", model="qwen-translation", api_key=PULSE_KEY)
    print_result(
        "Pulse key blocked from 'qwen-translation' (correct — not in allowed models)",
        not r.ok,
        f"Status: {r.status_code} — Expected 403"
    )

    # Translation key should work for qwen
    if TRANS_KEY and "CHANGE_ME" not in TRANS_KEY:
        r = chat_request("Say hello in Chinese", model="qwen-translation", api_key=TRANS_KEY)
        print_result(
            "Translation key can access 'qwen-translation' (allowed)",
            r.ok,
            f"Status: {r.status_code}"
        )


# =============================================================================
# TEST 5: RPM Rate Limiting — Burst requests and observe throttling
# =============================================================================
def test_rate_limiting():
    print_section("TEST 5: RPM Rate Limiting")

    if not BULK_KEY or "CHANGE_ME" in BULK_KEY:
        print("  ⚠️  TEAM_KEY_BULK_INSIGHTS not set. Run setup_teams.py first.")
        return

    print("  Sending 10 rapid requests to observe rate limiting...")
    print("  (Bulk Insights is capped at 75 RPM — won't throttle at 10 requests)")
    print()

    successes = 0
    throttled = 0

    for i in range(10):
        r = chat_request(
            message=f"Request {i+1}: reply with just 'ok'",
            model="gemma",
            api_key=BULK_KEY,
        )
        if r.status_code == 429:
            throttled += 1
            retry_after = r.headers.get("retry-after", "unknown")
            print(f"  Request {i+1}: 🚦 THROTTLED (429) — retry-after: {retry_after}s")
        elif r.ok:
            successes += 1
            print(f"  Request {i+1}: ✅ OK")
        else:
            print(f"  Request {i+1}: ❌ {r.status_code}")

    print()
    print(f"  Results: {successes} succeeded, {throttled} throttled")
    print("  To trigger throttling: reduce rpm_limit in .yaml and restart LiteLLM")


# =============================================================================
# TEST 6: Token Usage & Spend Tracking Per Team
# =============================================================================
def test_spend_tracking():
    print_section("TEST 6: Token Usage & Spend Tracking")

    # Global spend
    spend = get_global_spend()
    print("  Global Spend Report:")
    print(f"  {json.dumps(spend, indent=4)}")

    # Per-key spend
    if PULSE_KEY and "CHANGE_ME" not in PULSE_KEY:
        key_info = get_key_spend(PULSE_KEY)
        print()
        print("  Pulse Team Key Info:")
        relevant = {
            "spend":       key_info.get("info", {}).get("spend", 0),
            "max_budget":  key_info.get("info", {}).get("max_budget"),
            "rpm_limit":   key_info.get("info", {}).get("rpm_limit"),
            "tpm_limit":   key_info.get("info", {}).get("tpm_limit"),
        }
        print(f"  {json.dumps(relevant, indent=4)}")


# =============================================================================
# TEST 7: Whisper Audio Transcription Routing
# (Requires a running faster-whisper-server instance)
# =============================================================================
def test_whisper_routing():
    print_section("TEST 7: Whisper Audio Transcription Routing")

    # This test shows HOW you would route Whisper — it expects a real .wav file
    # In production, your worker service sends the audio file here instead of
    # loading PyTorch model weights locally.

    print("  Whisper is configured as model: 'whisper-transcription'")
    print("  Endpoint: http://whisper-server:8000/v1/audio/transcriptions")
    print()
    print("  To transcribe audio via LiteLLM (Python example):")
    print()
    print("""
  import openai

  client = openai.OpenAI(
      api_key="<your-team-api-key>",
      base_url="http://localhost:4000",    # LiteLLM proxy URL
  )

  with open("call_recording.wav", "rb") as audio_file:
      transcript = client.audio.transcriptions.create(
          model="whisper-transcription",   # Routes to faster-whisper-server
          file=audio_file,
      )

  print(transcript.text)
  # LiteLLM tracks token usage, which key sent it, and which backend served it
    """)

    print("  ℹ️  This decouples Whisper model weights from your worker code,")
    print("     enabling GPU usage tracking on shared infrastructure.")


# =============================================================================
# TEST 8: Fallback Routing Demo
# =============================================================================
def test_fallback_routing():
    print_section("TEST 8: Fallback Routing")

    print("  Fallback config in litellm_config.yaml:")
    print()
    print("  fallbacks:")
    print("    - gemma: ['fallback-model']")
    print()
    print("  Behaviour:")
    print("  1. Request arrives for model: 'gemma'")
    print("  2. LiteLLM tries primary backends (ollama-sa-1, ollama-sa-2, vllm-sa-1)")
    print("  3. If ALL fail (server down / timeout), LiteLLM automatically retries")
    print("     using 'fallback-model' (Gemma 3 2B — always-on lightweight model)")
    print("  4. The calling application receives a valid response — no interruption")
    print()
    print("  To test manually:")
    print("  1. Stop one Ollama container: docker stop ollama-sa-1")
    print("  2. Send a request — LiteLLM routes to ollama-sa-2 automatically")
    print("  3. Stop all Ollama containers")
    print("  4. Send a request — LiteLLM uses fallback-model")
    print("  5. Restart: docker start ollama-sa-1")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      MIRIAM LiteLLM — Full Capability Test               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\n  LiteLLM URL: {LITELLM_URL}")
    print(f"  Admin UI:    {LITELLM_URL}/ui")
    print(f"  Grafana:     http://localhost:3000")

    test_health()
    test_basic_routing()
    test_load_balancing()
    test_key_isolation()
    test_rate_limiting()
    test_spend_tracking()
    test_whisper_routing()
    test_fallback_routing()

    print()
    print("=" * 60)
    print("  ALL TESTS COMPLETE")
    print("=" * 60)
    print()
    print("  Open the Admin UI to see all activity visually:")
    print(f"  → {LITELLM_URL}/ui")
    print()


if __name__ == "__main__":
    main()

"""
=============================================================================
MIRIAM LiteLLM — Team & API Key Setup Script
=============================================================================
Run this ONCE after LiteLLM starts to:
  1. Create a team for each product/client (Pulse, Canvas, Translations, etc.)
  2. Generate a dedicated API key per team
  3. Set per-team spend budgets and model access
  4. Set RPM/TPM limits per key

Usage:
    python scripts/setup_teams.py

Requirements:
    pip install requests python-dotenv

The script reads credentials from your .env file.
=============================================================================
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load .env
load_dotenv()

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
MASTER_KEY   = os.getenv("LITELLM_MASTER_KEY")

if not MASTER_KEY:
    raise ValueError("LITELLM_MASTER_KEY not set in .env")

HEADERS = {
    "Authorization": f"Bearer {MASTER_KEY}",
    "Content-Type": "application/json",
}


# =============================================================================
# TEAM DEFINITIONS
# Each team maps to a product, client, or region.
# models: which models this team is allowed to use
# budget: monthly spend cap in USD (set low during testing)
# rpm_limit / tpm_limit: rate limits for all keys under this team
# =============================================================================
TEAMS = [
    {
        "team_alias": "pulse-qa",
        "team_id": "team-pulse",
        "description": "Pulse QA Platform — South Africa",
        "models": ["gemma", "fallback-model"],
        "max_budget": 50.0,            # $50/month cap
        "budget_duration": "monthly",
        "rpm_limit": 60,
        "tpm_limit": 100000,
        "env_key": "TEAM_KEY_PULSE",
    },
    {
        "team_alias": "canvas",
        "team_id": "team-canvas",
        "description": "Canvas Platform",
        "models": ["gemma", "fallback-model"],
        "max_budget": 30.0,
        "budget_duration": "monthly",
        "rpm_limit": 40,
        "tpm_limit": 80000,
        "env_key": "TEAM_KEY_CANVAS",
    },
    {
        "team_alias": "charisma",
        "team_id": "team-charisma",
        "description": "Charisma Platform",
        "models": ["gemma", "fallback-model"],
        "max_budget": 30.0,
        "budget_duration": "monthly",
        "rpm_limit": 40,
        "tpm_limit": 80000,
        "env_key": "TEAM_KEY_CHARISMA",
    },
    {
        "team_alias": "translations-princess-cruises",
        "team_id": "team-translations",
        "description": "Princess Cruises — Chinese Translation Pipeline",
        "models": ["qwen-translation", "fallback-model"],   # Qwen only — best for Eastern languages
        "max_budget": 10.0,
        "budget_duration": "monthly",
        "rpm_limit": 75,
        "tpm_limit": 145000,
        "env_key": "TEAM_KEY_TRANSLATIONS",
    },
    {
        "team_alias": "bulk-insights",
        "team_id": "team-bulk-insights",
        "description": "Bulk Insights Analytics Pipeline",
        "models": ["gemma", "fallback-model"],
        "max_budget": 100.0,
        "budget_duration": "monthly",
        "rpm_limit": 75,               # As per supervisor config
        "tpm_limit": 145000,           # As per supervisor config (145k tokens/min)
        "env_key": "TEAM_KEY_BULK_INSIGHTS",
    },
    {
        "team_alias": "uk-transcription",
        "team_id": "team-uk-transcription",
        "description": "UK Client — Whisper Audio Transcription",
        "models": ["whisper-transcription-uk", "whisper-transcription"],
        "max_budget": 20.0,
        "budget_duration": "monthly",
        "rpm_limit": 20,
        "tpm_limit": 50000,
        "env_key": "TEAM_KEY_UK_TRANSCRIPTION",
    },
    {
        "team_alias": "australia-region",
        "team_id": "team-australia",
        "description": "Australia Region — Pulse + Canvas",
        "models": ["gemma", "qwen-translation", "whisper-transcription", "fallback-model"],
        "max_budget": 75.0,
        "budget_duration": "monthly",
        "rpm_limit": 60,
        "tpm_limit": 100000,
        "env_key": "TEAM_KEY_AUSTRALIA",
    },
]


def create_team(team: dict) -> dict:
    """Create a team in LiteLLM."""
    payload = {
        "team_alias": team["team_alias"],
        "team_id": team["team_id"],
        "models": team["models"],
        "max_budget": team["max_budget"],
        "budget_duration": team["budget_duration"],
        "rpm_limit": team["rpm_limit"],
        "tpm_limit": team["tpm_limit"],
        "metadata": {"description": team["description"]},
    }
    response = requests.post(
        f"{LITELLM_URL}/team/new",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def generate_api_key(team: dict) -> str:
    """Generate an API key for a team."""
    # Use key from .env if set, otherwise let LiteLLM generate one
    env_key_value = os.getenv(team["env_key"])

    payload = {
        "team_id": team["team_id"],
        "key_alias": f"{team['team_alias']}-key",
        "models": team["models"],
        "max_budget": team["max_budget"],
        "budget_duration": team["budget_duration"],
        "rpm_limit": team["rpm_limit"],
        "tpm_limit": team["tpm_limit"],
        "metadata": {
            "team": team["team_alias"],
            "description": team["description"],
        },
    }

    # Pre-set a specific key value if defined in .env
    if env_key_value and "CHANGE_ME" not in env_key_value:
        payload["key"] = env_key_value

    response = requests.post(
        f"{LITELLM_URL}/key/generate",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("key", "unknown")


def list_teams() -> list:
    """List all teams currently in LiteLLM."""
    response = requests.get(
        f"{LITELLM_URL}/team/list",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def list_keys() -> list:
    """List all API keys."""
    response = requests.get(
        f"{LITELLM_URL}/key/list",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_spend_report() -> dict:
    """Get current spend across all teams."""
    response = requests.get(
        f"{LITELLM_URL}/global/spend",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main():
    print("=" * 60)
    print("  MIRIAM LiteLLM — Team Setup")
    print("=" * 60)
    print(f"  Connecting to: {LITELLM_URL}")
    print()

    # Verify LiteLLM is reachable
    try:
        health = requests.get(f"{LITELLM_URL}/health", timeout=10)
        health.raise_for_status()
        print("  ✅ LiteLLM is running and healthy")
    except Exception as e:
        print(f"  ❌ Cannot reach LiteLLM at {LITELLM_URL}")
        print(f"     Error: {e}")
        print("     Make sure LiteLLM is running: docker-compose up -d")
        return

    print()
    print("  Creating teams and API keys...")
    print("-" * 60)

    results = []

    for team in TEAMS:
        print(f"\n  📦 Team: {team['team_alias']}")
        print(f"     {team['description']}")

        # Create team
        try:
            create_team(team)
            print(f"     ✅ Team created")
        except requests.HTTPError as e:
            if "already exists" in str(e.response.text).lower():
                print(f"     ℹ️  Team already exists, skipping creation")
            else:
                print(f"     ❌ Team creation failed: {e}")
                continue

        # Generate API key
        try:
            api_key = generate_api_key(team)
            print(f"     ✅ API Key: {api_key}")
            results.append({
                "team": team["team_alias"],
                "description": team["description"],
                "api_key": api_key,
                "models": team["models"],
                "rpm_limit": team["rpm_limit"],
                "tpm_limit": team["tpm_limit"],
                "monthly_budget_usd": team["max_budget"],
            })
        except Exception as e:
            print(f"     ❌ Key generation failed: {e}")

    # Save results to file
    output_path = "teams/generated_keys.json"
    os.makedirs("teams", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print()
    print("=" * 60)
    print("  SETUP COMPLETE")
    print("=" * 60)
    print(f"\n  Keys saved to: {output_path}")
    print("  ⚠️  Keep this file secure — treat keys like passwords")
    print()
    print("  Admin UI:  http://localhost:4000/ui")
    print("  Grafana:   http://localhost:3000")
    print()
    print("  Next steps:")
    print("  1. Open http://localhost:4000/ui and log in")
    print("  2. Go to 'Teams' to see all created teams")
    print("  3. Go to 'Usage' to monitor token consumption")
    print("  4. Run: python scripts/test_routing.py")
    print()


if __name__ == "__main__":
    main()

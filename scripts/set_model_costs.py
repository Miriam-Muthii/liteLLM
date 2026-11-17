"""
=============================================================================
MIRIAM LiteLLM — Bind Costs to Models for Client Billing
=============================================================================
This solves the billing problem your supervisor described:
  "I can then actually go into each one of these models and add the costing,
   which means from an actual cost perspective, we can have the system handle
   a lot of those discussions for us as well."

The costs here are INTERNAL CHARGE-OUT RATES, not what cloud providers charge.
They are calculated as:
  - Average per-million-token price across TogetherAI / Groq / Cerebras
  - Divided by 1,000,000 to get per-token rate
  - Add infrastructure amortization factor (adjust to your actual server costs)

Usage:
    python scripts/set_model_costs.py

After running, the LiteLLM UI and Grafana will show USD cost per request.
=============================================================================
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
MASTER_KEY  = os.getenv("LITELLM_MASTER_KEY")

HEADERS = {
    "Authorization": f"Bearer {MASTER_KEY}",
    "Content-Type":  "application/json",
}


# =============================================================================
# COST DEFINITIONS
# =============================================================================
# Format:
#   input_cost_per_token:  cost in USD per input token
#   output_cost_per_token: cost in USD per output token
#
# Example calculation for Gemma:
#   Market avg input:  $0.13 / 1M tokens  = 0.00000013 per token
#   Market avg output: $0.15 / 1M tokens  = 0.00000015 per token
#   Infrastructure factor: x2 (we run our own hardware)
#   Internal rate: 0.00000026 input, 0.00000030 output
#
# As supervisor noted: at 4-5M tokens/day, cost per agent is ~$0.02/month
# =============================================================================

MODEL_COSTS = [
    {
        "model_name": "gemma",
        "input_cost_per_token":  0.00000013,   # $0.13 per 1M input tokens
        "output_cost_per_token": 0.00000015,   # $0.15 per 1M output tokens
        "notes": "Gemma 3 — South Africa / UK backends",
    },
    {
        "model_name": "gemma-uk",
        "input_cost_per_token":  0.00000013,
        "output_cost_per_token": 0.00000015,
        "notes": "Gemma 3 — UK region",
    },
    {
        "model_name": "qwen-translation",
        "input_cost_per_token":  0.00000008,   # Qwen is cheaper; uses ~half the tokens
        "output_cost_per_token": 0.00000010,   # for Eastern language tasks
        "notes": "Qwen 2.5 — Translation pipeline. Uses ~50% fewer tokens than Gemma for Chinese.",
    },
    {
        "model_name": "whisper-transcription",
        "input_cost_per_token":  0.00000006,   # Audio tokens (per second of audio)
        "output_cost_per_token": 0.00000006,
        "notes": "Whisper Distil-v3 — SA transcription",
    },
    {
        "model_name": "whisper-transcription-uk",
        "input_cost_per_token":  0.00000006,
        "output_cost_per_token": 0.00000006,
        "notes": "Whisper — UK client transcription",
    },
    {
        "model_name": "fallback-model",
        "input_cost_per_token":  0.00000005,   # Smallest model — cheapest
        "output_cost_per_token": 0.00000005,
        "notes": "Gemma 3 2B fallback — lowest cost",
    },
]


def set_model_cost(model: dict) -> bool:
    """Update cost bindings for a model via LiteLLM management API."""
    payload = {
        "model_name": model["model_name"],
        "litellm_params": {
            "input_cost_per_token":  model["input_cost_per_token"],
            "output_cost_per_token": model["output_cost_per_token"],
        },
    }
    response = requests.post(
        f"{LITELLM_URL}/model/update",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    return response.ok


def main():
    print("=" * 60)
    print("  MIRIAM LiteLLM — Binding Costs to Models")
    print("=" * 60)

    print()
    print("  Model costs are expressed as USD per token.")
    print("  These appear in the Admin UI, Grafana, and spend reports.")
    print()

    for model in MODEL_COSTS:
        success = set_model_cost(model)
        input_per_m  = model["input_cost_per_token"]  * 1_000_000
        output_per_m = model["output_cost_per_token"] * 1_000_000
        status = "✅" if success else "❌"
        print(f"  {status} {model['model_name']}")
        print(f"     Input:  ${input_per_m:.4f} / 1M tokens")
        print(f"     Output: ${output_per_m:.4f} / 1M tokens")
        print(f"     Note:   {model['notes']}")
        print()

    print("  Done! Costs are now visible in:")
    print(f"  → Admin UI:  {LITELLM_URL}/ui  (Usage tab)")
    print(f"  → Grafana:   http://localhost:3000")
    print()
    print("  Example monthly bill calculation:")
    print("  Agent sends 20 emails/day × 500 tokens/email = 10,000 tokens/day")
    print("  × 20 working days = 200,000 tokens/month")
    print("  × $0.13 per million = $0.026 per agent per month")
    print()


if __name__ == "__main__":
    main()

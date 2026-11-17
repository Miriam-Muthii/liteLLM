# LiteLLM Exploration Guide
**Project:** MIRIAM LiteLLM Gateway
**Last updated:** 2026-11-17

---

## Table of Contents
1. [What is running and where](#1-what-is-running-and-where)
2. [Logging in to the Admin UI](#2-logging-in-to-the-admin-ui)
3. [Exploring the Admin UI](#3-exploring-the-admin-ui)
4. [Creating a Team](#4-creating-a-team)
5. [Creating API Keys](#5-creating-api-keys)
6. [Testing a Request through the Proxy](#6-testing-a-request-through-the-proxy)
7. [Observability - Prometheus](#7-observability--prometheus)
8. [Observability - Grafana](#8-observability--grafana)
9. [Connecting Prometheus to Grafana](#9-connecting-prometheus-to-grafana)
10. [Running the Setup Scripts](#10-running-the-setup-scripts)
11. [Understanding the Config File](#11-understanding-the-config-file)
12. [Common curl Commands Cheat Sheet](#12-common-curl-commands-cheat-sheet)

---

## 1. What is running and where

After `docker-compose up -d`, four containers start:

| Container | Purpose | URL |
|---|---|---|
| `miriam-litellm` | The AI proxy - routes requests, enforces keys and limits | http://localhost:4000 |
| `miriam-postgres` | Database - stores keys, teams, spend data | port 5432 |
| `miriam-prometheus` | Metrics collector - scrapes LiteLLM every 15s | http://localhost:9090 |
| `miriam-grafana` | Dashboard - visualises Prometheus metrics | http://localhost:3001 |

Check all are running:

    docker-compose ps

View live logs from LiteLLM:

    docker-compose logs -f litellm

---

## 2. Logging in to the Admin UI

Open http://localhost:4000/ui

| Field | Value |
|---|---|
| Username | admin |
| Password | sk-miriam-master-e315c1250234bd6c9fce776aec357a74b196654e |

IMPORTANT: Keep the master key secret. It is stored in litellm-project/.env
which is listed in .gitignore and must never be committed to Git.

---

## 3. Exploring the Admin UI

Once logged in you will see tabs across the top. Here is what each section does:

### Dashboard
- Shows total requests, tokens used, errors, and spend in real time
- Changes as you send requests through the proxy
- Nothing will show until you send at least one request

### Models
- Lists every model defined in config/litellm_config.yaml
- You can see local-gemma, gemma, gemma-uk, qwen-translation, whisper-transcription, etc.
- Click a model to see its backends, RPM/TPM limits, and health

### Virtual Keys
- API keys issued to teams or users
- Each key has a spend budget, rate limit, and allowed model list
- You can create, revoke, and inspect keys here

### Teams
- Groups of keys with shared budgets and permissions
- E.g. pulse-qa, canvas, charisma
- Teams are created either via the UI or via the scripts/setup_teams.py script

### Spend Logs
- Every request that passed through the proxy is logged here
- Shows model used, tokens in/out, estimated cost, and which key made the call
- This is the billing evidence your supervisor asked about

---

## 4. Creating a Team

Teams represent a product or business unit. Each team gets its own budget, rate limits, and allowed model list.

### Via the Admin UI
1. Go to Teams > + New Team
2. Fill in:
   - Team ID: e.g. pulse-qa
   - Team Alias: e.g. Pulse QA Platform
   - Models: select which models this team can use
   - Max Budget: e.g. 50 (USD per month)
   - RPM Limit: e.g. 100
3. Click Create Team

### Via the script (creates all 7 teams at once)

    cd C:\Users\GCA17690\Documents\MIRIAM\PROJECTS\litellm-project
    pip install -r requirements.txt
    python scripts/setup_teams.py

This creates teams for: Pulse QA, Canvas, Charisma, Princess Cruises translations,
Bulk Insights, UK Transcription, and Australia region.
Keys are saved to teams/generated_keys.json.

---

## 5. Creating API Keys

A key is what an application uses to authenticate with LiteLLM.
Each key belongs to a team and inherits its limits.

### Via the Admin UI
1. Go to Virtual Keys > + Create Key
2. Fill in:
   - Key Name: e.g. pulse-qa-prod
   - Team: select pulse-qa
   - Models: leave blank to inherit team models
   - Max Budget: leave blank to inherit team budget
3. Click Create Key
4. COPY THE KEY IMMEDIATELY - it is only shown once

### Via the API (PowerShell)

    curl http://localhost:4000/key/generate `
      -H "Authorization: Bearer sk-miriam-master-e315c1250234bd6c9fce776aec357a74b196654e" `
      -H "Content-Type: application/json" `
      -d '{"team_id": "pulse-qa", "key_alias": "pulse-qa-prod", "models": ["gemma"], "max_budget": 50}'

---

## 6. Testing a Request through the Proxy

LiteLLM exposes an OpenAI-compatible API, so any tool that speaks OpenAI works with it.

### Health check (no key needed)

    curl http://localhost:4000/health

### List available models

    curl http://localhost:4000/models -H "Authorization: Bearer sk-miriam-master-e315c1250234bd6c9fce776aec357a74b196654e"

### Send a chat request (requires Ollama running locally with gemma3:2b pulled)

    curl http://localhost:4000/chat/completions `
      -H "Authorization: Bearer sk-miriam-master-e315c1250234bd6c9fce776aec357a74b196654e" `
      -H "Content-Type: application/json" `
      -d '{"model": "local-gemma", "messages": [{"role": "user", "content": "Say hello in one sentence."}]}'

To use local-gemma: download Ollama from https://ollama.ai/download then run:

    ollama pull gemma3:2b

### Test with Python

    from openai import OpenAI

    client = OpenAI(
        api_key="sk-miriam-master-e315c1250234bd6c9fce776aec357a74b196654e",
        base_url="http://localhost:4000",
    )
    response = client.chat.completions.create(
        model="local-gemma",
        messages=[{"role": "user", "content": "Hello, what model are you?"}]
    )
    print(response.choices[0].message.content)

### Run the full capability test suite

    python scripts/test_routing.py

---

## 7. Observability - Prometheus

Prometheus collects metrics from LiteLLM every 15 seconds.
LiteLLM exposes a /metrics endpoint that Prometheus scrapes automatically.

Open http://localhost:9090

### Useful queries - paste into the Prometheus search bar and click Execute

| What you want to see | Query |
|---|---|
| Total requests to LiteLLM | litellm_requests_metric_total |
| Total tokens used | litellm_total_tokens |
| Input tokens by model | litellm_input_tokens |
| Output tokens by model | litellm_output_tokens |
| Failed requests | litellm_deployment_failure_responses |
| Requests per second (last 5 min) | rate(litellm_requests_metric_total[5m]) |
| Token spend rate | rate(litellm_total_tokens[5m]) |

### How the scrape works
1. LiteLLM runs at http://localhost:4000
2. Prometheus reads config/prometheus.yml which says: scrape http://litellm:4000/metrics every 15s
3. Every request you send through LiteLLM increments the counters at /metrics
4. Prometheus stores those numbers as time-series data
5. Grafana reads from Prometheus to draw charts

---

## 8. Observability - Grafana

Grafana connects to Prometheus and turns raw metrics into visual dashboards.

Open http://localhost:3001

| Field | Value |
|---|---|
| Username | admin |
| Password | Monitor50fb4cb112e23aed |

---

## 9. Connecting Prometheus to Grafana

One-time setup step.

### Step 1 - Add Prometheus as a data source
1. In Grafana, click the hamburger menu (three lines top-left) > Connections > Data sources
2. Click + Add new data source
3. Select Prometheus
4. Set the URL to: http://miriam-prometheus:9090
   (Use the Docker container name, NOT localhost - both are on the same Docker network)
5. Click Save & test - you should see "Successfully queried the Prometheus API"

### Step 2 - Import the official LiteLLM dashboard
1. Click the hamburger menu > Dashboards > Import
2. Enter Dashboard ID: 20764
3. Click Load
4. Select your Prometheus data source from the dropdown
5. Click Import

You now have a full LiteLLM dashboard with request rates, token counts,
model usage breakdown, and error rates.

### Step 3 - Send requests to see data
Run the test script or send a few curl requests, then refresh the dashboard.
Data appears within 15-30 seconds of requests being processed.

---

## 10. Running the Setup Scripts

Three scripts are included in the scripts/ folder.

### setup_teams.py - Run once after containers start
Creates all 7 teams and their API keys in LiteLLM via the API.

    python scripts/setup_teams.py

Output: teams/generated_keys.json  (keep this file secure - do not commit to Git)

### set_model_costs.py - Run after setup_teams.py
Binds USD costs to each model so the spend tracker shows real dollar amounts.

    python scripts/set_model_costs.py

After this, the Admin UI Spend Logs tab shows cost per request.

### test_routing.py - Run any time to verify the system
Runs an end-to-end test covering:
- Health check
- Basic chat routing
- Load balancing between backends
- Key isolation (a Pulse key cannot use a Canvas model)
- RPM rate limiting
- Spend tracking
- Fallback routing
- Whisper transcription routing

    python scripts/test_routing.py

---

## 11. Understanding the Config File

config/litellm_config.yaml controls everything about how the proxy behaves.

### model_list
Each entry defines one backend. Multiple entries with the SAME model_name
form a load-balanced pool automatically.

    # Two entries, same model_name = auto load balanced
    - model_name: gemma
      litellm_params:
        api_base: http://ollama-sa-1:11434   # Server 1

    - model_name: gemma
      litellm_params:
        api_base: http://ollama-sa-2:11434   # Server 2

### router_settings
Controls how traffic is split across backends:
- least-busy: fewest active requests (default, good for mixed load)
- latency-based-routing: fastest responding server
- usage-based-routing: most remaining RPM capacity
- simple-shuffle: random (good for identical servers)

### After editing the config, restart LiteLLM to reload it:

    docker-compose restart litellm

---

## 12. Common curl Commands Cheat Sheet

Replace MASTER below with:
sk-miriam-master-e315c1250234bd6c9fce776aec357a74b196654e

    # Health check (no auth needed)
    curl http://localhost:4000/health

    # List models
    curl http://localhost:4000/models -H "Authorization: Bearer MASTER"

    # List all teams
    curl http://localhost:4000/team/list -H "Authorization: Bearer MASTER"

    # List all keys
    curl http://localhost:4000/key/list -H "Authorization: Bearer MASTER"

    # View global spend (USD)
    curl http://localhost:4000/global/spend -H "Authorization: Bearer MASTER"

    # View spend by team
    curl http://localhost:4000/global/spend/teams -H "Authorization: Bearer MASTER"

    # Generate a new key for pulse-qa team
    curl http://localhost:4000/key/generate ^
      -H "Authorization: Bearer MASTER" ^
      -H "Content-Type: application/json" ^
      -d "{\"team_id\": \"pulse-qa\", \"key_alias\": \"my-test-key\", \"max_budget\": 10}"

    # Send a chat request
    curl http://localhost:4000/chat/completions ^
      -H "Authorization: Bearer MASTER" ^
      -H "Content-Type: application/json" ^
      -d "{\"model\": \"local-gemma\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}"

---

## Stopping and restarting

    # Stop everything (volumes and data are preserved)
    docker-compose down

    # Stop and wipe all data (clean slate - you lose all keys and spend history)
    docker-compose down -v

    # Restart just LiteLLM after a config change
    docker-compose restart litellm

    # View all container logs
    docker-compose logs -f

---

## Next steps

Once you are comfortable with the basics:

1. Connect a real Ollama server - update api_base entries in litellm_config.yaml
   to point to your actual GPU servers (replace ollama-sa-1, ollama-sa-2 etc.)
2. Run setup_teams.py - creates all 7 teams automatically
3. Run set_model_costs.py - bind USD costs to models for accurate billing reports
4. Import Grafana dashboard ID 20764 - full visual monitoring in one click
5. Explore the Spend Logs tab in the Admin UI after sending requests -
   this is the per-team billing evidence your supervisor described

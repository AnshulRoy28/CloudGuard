<p align="center">
  <img src="https://img.shields.io/badge/GCP-Cloud%20Run-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
</p>

<h1 align="center">🛡️ CloudGuard</h1>
<h3 align="center">Autonomous FinOps Agent for Google Cloud</h3>

<p align="center">
  <b>Stop waking up to surprise cloud bills.</b><br>
  CloudGuard monitors your GCP spending 24/7, detects anomalies, and lets you take action with one click from your inbox.
</p>

---

## 🎯 The Problem

Students and developers spin up cloud resources, forget about them, and get hit with unexpected bills. GCP's built-in budget alerts are slow (up to 24-hour delay) and don't let you take immediate action.

## ⚡ The Solution

CloudGuard runs on Cloud Run and checks your billing data every hour. When it detects unusual spending, it sends you an email with **one-click action buttons** — stop the instance, snapshot & stop, or dismiss — all without logging into the GCP Console.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Anomaly Detection** | Statistical baseline tracking with configurable sensitivity |
| 📧 **Email Alerts** | Beautiful HTML emails via SendGrid with cost breakdowns |
| 🖱️ **One-Click Actions** | Stop instances or create snapshots directly from email |
| 🔐 **Secure by Design** | JWT-signed action links, rate limiting, blocklist protection |
| 🏗️ **Infrastructure as Code** | Terraform modules for automated GCP setup |
| 🐳 **Containerized** | Docker + Cloud Run for serverless, always-on deployment |
| ⏰ **Scheduled Checks** | Cloud Scheduler triggers hourly cost reviews |
| 🛡️ **Safety Rails** | Dry-run mode, production blocklists, high-cost confirmations |

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Cloud Scheduler │────▶│   CloudGuard API  │────▶│    BigQuery      │
│  (hourly cron)   │     │   (Cloud Run)     │     │  (billing data)  │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌───────────┐ ┌──────────┐ ┌──────────┐
             │  SendGrid  │ │  Compute │ │  Secret  │
             │  (emails)  │ │  Engine  │ │  Manager │
             └───────────┘ └──────────┘ └──────────┘
```

**How it works:**
1. **Cloud Scheduler** triggers the `/api/v1/check` endpoint every hour
2. **Watcher** queries BigQuery for current month spending
3. **Anomaly Detector** compares against a rolling baseline
4. If anomaly detected → **SendGrid** sends an alert email with JWT-signed action buttons
5. User clicks a button → **GCP Executor** stops/snapshots the resource (after safety checks)

## 📂 Project Structure

```
CloudGuard/
├── src/
│   ├── api/                  # FastAPI application
│   │   ├── main.py           # API endpoints (health, execute, check)
│   │   ├── jwt_handler.py    # JWT token generation & validation
│   │   ├── gcp_executor.py   # Compute Engine operations
│   │   └── safety_rules.py   # Blocklist, rate limits, confirmations
│   ├── data/
│   │   ├── bigquery_client.py # Billing data queries
│   │   └── queries.sql       # SQL query templates
│   ├── notifications/
│   │   └── email_service.py  # SendGrid email integration
│   ├── watcher/
│   │   └── watcher.py        # Anomaly detection & orchestration
│   └── config.py             # Environment configuration
├── infrastructure/
│   └── terraform/            # GCP infrastructure as code
├── templates/
│   └── alert_email.html      # Email template (Jinja2)
├── scripts/
│   ├── setup.py              # Interactive setup wizard
│   ├── deploy.ps1            # Windows deployment script
│   └── deploy.sh             # Linux/macOS deployment script
├── Dockerfile                # Container configuration
├── requirements.txt          # Python dependencies
└── QUICKSTART.md             # 5-minute setup guide
```

## 🚀 Quick Start

See **[QUICKSTART.md](QUICKSTART.md)** for a 5-minute setup guide.

**TL;DR:**
```bash
# 1. Clone & install
git clone https://github.com/AnshulRoy28/CloudGuard.git
cd CloudGuard
pip install -r requirements.txt

# 2. Run setup wizard
python scripts/setup.py

# 3. Deploy to Cloud Run
.\scripts\deploy.ps1        # Windows
bash scripts/deploy.sh      # Linux/macOS
```

## 🔒 Security

- **No hardcoded secrets** — all credentials stored in `.env` (local) or GCP Secret Manager (production)
- **JWT-signed action links** — 4-hour expiry with unique token IDs
- **Rate limiting** — max 3 actions per hour per user
- **Production blocklist** — resources tagged `production`, `prod`, or `critical` are protected
- **Dry-run mode** — enabled by default, no resources modified until you're ready
- **Non-root container** — runs as unprivileged user in Docker

## ⚙️ Configuration

All config is managed via environment variables (`.env` file):

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Your GCP project ID | *required* |
| `ALERT_EMAIL` | Email for alerts | *required* |
| `SENDGRID_API_KEY` | SendGrid API key | *required* |
| `MONTHLY_BUDGET_LIMIT` | Budget threshold (USD) | `100` |
| `ANOMALY_SENSITIVITY` | Standard deviations for anomaly | `2.5` |
| `DRY_RUN_MODE` | Log actions without executing | `true` |
| `BLOCKLIST_TAGS` | Protected resource tags | `production,prod,critical` |
| `MAX_ACTIONS_PER_HOUR` | Rate limit per user | `3` |

See [`.env.example`](.env.example) for the full list.

## 🧪 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + deployment status |
| `/api/v1/check` | GET | Trigger cost check (used by scheduler) |
| `/api/v1/execute/{action}` | GET | Execute remediation action via JWT |
| `/api/v1/test-email` | GET | Send a test alert email |

## 💡 Built For Students

CloudGuard was built to solve a real problem: students learning cloud computing shouldn't have to worry about accidental $200 bills from forgotten GPU instances. It runs entirely on GCP's free tier:

- **Cloud Run** — free for low-traffic services
- **BigQuery** — first 1TB/month of queries free
- **Cloud Scheduler** — 3 free jobs per account
- **SendGrid** — 100 emails/day on free tier

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>Built with ❤️ to save students from cloud bill nightmares</b>
</p>

# ⚡ CloudGuard Quick Start Guide

Get CloudGuard running in **5 minutes**. This guide covers everything from prerequisites to a live deployment.

---

## Prerequisites

| Tool | Install Link | Check Command |
|------|-------------|---------------|
| **Python 3.11+** | [python.org](https://www.python.org/downloads/) | `python --version` |
| **Google Cloud SDK** | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) | `gcloud --version` |
| **Docker Desktop** | [docker.com](https://www.docker.com/products/docker-desktop/) | `docker --version` |
| **Terraform** | [terraform.io](https://www.terraform.io/downloads) | `terraform --version` |

You'll also need:
- A **GCP project** with billing enabled
- A **SendGrid account** ([free tier](https://sendgrid.com/) — 100 emails/day)

---

## Step 1: Clone & Install

```bash
git clone https://github.com/AnshulRoy28/CloudGuard.git
cd CloudGuard
pip install -r requirements.txt
```

## Step 2: Run the Setup Wizard

```bash
python scripts/setup.py
```

The wizard will:
1. ✅ Check prerequisites (gcloud, Terraform)
2. 🏗️ Run Terraform to create GCP infrastructure (service account, BigQuery dataset, IAM)
3. 🔗 Guide you through billing export setup
4. 🔑 Walk you through API key configuration (SendGrid + optional Gemini)
5. 📝 Generate your `.env` configuration file

## Step 3: Set Up SendGrid (Important!)

CloudGuard needs SendGrid to send alert emails. The setup wizard guides you through this, but here's a summary:

### 3a. Create an API Key
1. Sign up at [sendgrid.com](https://sendgrid.com/)
2. Go to **Settings → API Keys**
3. Click **"Create API Key"** → select **"Restricted Access"**
4. Enable **"Mail Send → Mail Send"** permission
5. Copy the key (starts with `SG.`)

### 3b. Verify Your Sender Email

> ⚠️ **This step is mandatory.** SendGrid rejects all emails from unverified senders.

1. Go to [Sender Authentication](https://app.sendgrid.com/settings/sender_auth/senders)
2. Click **"Create New Sender"**
3. Fill in the form:

| Field | What to enter |
|-------|--------------|
| From Name | Your name |
| From Email | Your email (same as `ALERT_EMAIL` in `.env`) |
| Reply To | Same email |
| Company Address | Any address (required by anti-spam law) |
| City / State / Zip | Your location |
| Country | Your country |
| Nickname | `CloudGuard Alerts` |

4. Click **Create**, then check your inbox for the verification email
5. Click the verification link

## Step 4: Test Locally

```bash
# Run the watcher to verify BigQuery connection
python src/watcher/watcher.py

# Start the API server locally
uvicorn src.api.main:app --host 0.0.0.0 --port 8080

# Visit http://localhost:8080/health
```

## Step 5: Deploy to Cloud Run

```powershell
# Windows
.\scripts\deploy.ps1
```

```bash
# Linux/macOS
bash scripts/deploy.sh
```

The deploy script will:
1. 🐳 Build and push the Docker image
2. 🔐 Store secrets in GCP Secret Manager
3. 🚀 Deploy to Cloud Run
4. ⏰ Create a Cloud Scheduler job (hourly checks)
5. ✅ Run a health check

## Step 6: Verify Deployment

After deployment, test these endpoints:

| Test | URL |
|------|-----|
| Health Check | `https://YOUR-SERVICE-URL/health` |
| Trigger Cost Check | `https://YOUR-SERVICE-URL/api/v1/check` |
| Test Email | `https://YOUR-SERVICE-URL/api/v1/test-email` |

Check that Cloud Scheduler is set up:
```bash
gcloud scheduler jobs list --location=us-central1
```

---

## 🎉 You're Done!

CloudGuard is now monitoring your GCP costs 24/7. Here's what happens next:

1. **Every hour**, Cloud Scheduler triggers a cost check
2. If spending exceeds your baseline, you'll get an **email alert**
3. Click the action buttons to **stop instances** or **create snapshots** — no console needed

### Useful Commands

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cloudguard-api" --limit=20

# Manually trigger a check
curl https://YOUR-SERVICE-URL/api/v1/check

# Update deployment after code changes
.\scripts\deploy.ps1
```

---

## ❓ Troubleshooting

| Issue | Fix |
|-------|-----|
| Health check returns `Missing required configuration` | Ensure all env vars are set in deploy script |
| Email says "Failed to send" | Verify your sender email in SendGrid |
| `$0.00` spend reported | Billing data takes ~24 hours to populate in BigQuery |
| Docker build fails | Run `docker build --no-cache -t IMAGE_NAME .` |

For more help, open an [issue on GitHub](https://github.com/AnshulRoy28/CloudGuard/issues).

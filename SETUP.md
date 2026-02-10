# CloudGuard AI - Automated Setup Guide

This guide explains the automated setup process for CloudGuard AI.

## 🚀 Quick Setup (3 Commands)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Run the setup wizard
python scripts/setup.py

# 3. Validate everything works
python scripts/validate.py
```

That's it! The setup wizard handles everything else.

## 📋 What the Setup Wizard Does

### Automatic (Terraform)
✅ Creates GCP service account with minimal permissions  
✅ Enables required APIs (BigQuery, Compute, Storage, Logging)  
✅ Creates BigQuery datasets (billing_export, audit logs)  
✅ Sets up IAM roles  
✅ Generates service account key  

### Interactive (Setup Wizard)
🔹 Guides you to configure billing export (GCP Console)  
🔹 Collects SendGrid API key  
🔹 Collects Gemini API key  
🔹 Asks for your alert email  
🔹 Configures budget threshold  
🔹 Generates `.env` file with all settings  
🔹 Creates JWT secret automatically  

### Validation
✔️ Checks all configuration files exist  
✔️ Validates service account permissions  
✔️ Tests BigQuery connection  
✔️ Verifies billing export is configured  
✔️ Confirms API keys are valid format  

## 🛠️ Prerequisites

Before running setup:

1. **gcloud CLI** installed
   ```bash
   # Check if installed
   gcloud --version
   
   # Install: https://cloud.google.com/sdk/docs/install
   ```

2. **Terraform** installed
   ```bash
   # Check if installed
   terraform --version
   
   # Install: https://www.terraform.io/downloads
   ```

3. **GCP Project** with billing enabled
   - Project must have billing enabled
   - You must have `Owner` or `Editor` role

4. **Authenticate gcloud**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```

## 📝 Step-by-Step Walkthrough

### Step 1: Run Setup Wizard

```bash
python scripts/setup.py
```

The wizard will:

1. **Check Prerequisites**
   - Verifies gcloud and terraform are installed
   - Gets your current GCP project

2. **Deploy Infrastructure (Terraform)**
   - Shows you what will be created
   - Asks for confirmation
   - Creates all GCP resources (~2-3 minutes)
   - Shows service account details

3. **Configure Billing Export**
   - Guides you to GCP Console
   - Shows exact steps to enable billing export
   - Waits for you to complete it

4. **Collect API Keys**
   - **SendGrid**: Free tier available (100 emails/day)
     - Sign up: https://sendgrid.com/
     - Create API key with "Mail Send" permission
   
   - **Gemini**: Free tier available
     - Get key: https://aistudio.google.com/apikey

5. **Configure Settings**
   - Your alert email address
   - Monthly budget limit (default: $100)
   - Dry run mode (recommended: yes for first 2 weeks)

6. **Generate Configuration**
   - Creates `.env` file with all your settings
   - Generates secure JWT secret
   - Saves service account key path

### Step 2: Validate Setup

```bash
python scripts/validate.py
```

This checks:
- ✅ .env file exists and is valid
- ✅ Service account key is present and valid
- ✅ Can connect to BigQuery
- ✅ Billing export dataset exists
- ✅ API keys are configured
- ✅ All required configuration values are set

If validation passes, you're ready to go!

### Step 3: Test the Watcher

```bash
python src/watcher/watcher.py
```

This runs one check cycle and shows:
- Current month-to-date spend
- Top cost contributors
- Anomaly detection results

## 🔧 Manual Setup (Alternative)

If you prefer manual setup or the wizard fails:

### 1. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create cloudguard-agent \
  --display-name="CloudGuard AI Agent"

# Grant permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:cloudguard-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:cloudguard-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/compute.instanceAdmin.v1"

# Download key
gcloud iam service-accounts keys create cloudguard-sa-key.json \
  --iam-account=cloudguard-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 2. Create BigQuery Datasets

```bash
bq mk --dataset --location=US billing_export
bq mk --dataset --location=US cloudguard_audit
```

### 3. Configure Billing Export

1. Go to: https://console.cloud.google.com/billing
2. Click: Billing Export → BigQuery Export
3. Click: Edit Settings
4. Select dataset: `billing_export`
5. Click: Save

### 4. Create .env File

Copy `.env.example` to `.env` and fill in all values.

## 🐛 Troubleshooting

### "gcloud not found"
Install: https://cloud.google.com/sdk/docs/install

### "terraform not found"
Install: https://www.terraform.io/downloads

### "Permission denied" during Terraform
You need `Owner` or `Editor` role on the GCP project.

### "Billing export dataset not found"
Billing export must be configured manually in GCP Console. The wizard guides you through this.

### "Service account key invalid"
Re-run Terraform or manually download a new key.

### Terraform fails with "already exists"
Resources may already exist. You can:
1. Import existing resources: `terraform import`
2. Or use existing resources and skip Terraform

## 📚 What's Next?

After successful setup:

1. **Phase 1 Testing**
   ```bash
   python src/watcher/watcher.py
   ```

2. **Continue Building**
   - Phase 2: AI Intelligence (Gemini analysis)
   - Phase 3: FastAPI Remediation Backend
   - Phase 4: Email Notifications
   - Phase 5: Deploy to Cloud Run

3. **Read Documentation**
   - `README.md` - Full project overview
   - `QUICKSTART.md` - Quick reference
   - Implementation plan (in artifacts)

## 💡 Tips

- **Dry run mode**: Keep enabled for 1-2 weeks to build confidence
- **Billing data delay**: Can take up to 24 hours to start flowing
- **Free tiers**: SendGrid (100 emails/day), Gemini (generous free tier)
- **Cost**: CloudGuard itself costs <$2/month to run

## 🆘 Need Help?

If setup fails:
1. Check error messages carefully
2. Run validation: `python scripts/validate.py`
3. Check `cloudguard.log` for details
4. Verify GCP project has billing enabled
5. Ensure you have proper IAM permissions

---

**Ready to get started?**

```bash
python scripts/setup.py
```

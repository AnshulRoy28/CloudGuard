#!/usr/bin/env python3
"""Interactive setup wizard for CloudGuard AI"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Optional

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def check_gcloud_installed() -> bool:
    """Check if gcloud CLI is installed"""
    try:
        subprocess.run(["gcloud", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # On Windows, try common installation paths
        if sys.platform == "win32":
            common_paths = [
                r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
                r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
                Path.home() / "AppData" / "Local" / "Google" / "Cloud SDK" / "google-cloud-sdk" / "bin" / "gcloud.cmd"
            ]
            
            for path in common_paths:
                try:
                    subprocess.run([str(path), "--version"], capture_output=True, check=True)
                    # Found it! Add to PATH for this session
                    os.environ["PATH"] = f"{Path(path).parent};{os.environ['PATH']}"
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
        
        return False


def check_terraform_installed() -> bool:
    """Check if Terraform is installed"""
    try:
        subprocess.run(["terraform", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # On Windows, try terraform.exe
        if sys.platform == "win32":
            try:
                subprocess.run(["terraform.exe", "--version"], capture_output=True, check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        return False




def get_gcloud_command() -> str:
    """Get the correct gcloud command for the current platform"""
    if sys.platform == "win32":
        # On Windows, prefer gcloud.cmd
        return "gcloud.cmd"
    return "gcloud"


def get_gcp_project_id() -> Optional[str]:
    """Get current GCP project ID"""
    try:
        gcloud_cmd = get_gcloud_command()
        result = subprocess.run(
            [gcloud_cmd, "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True
        )
        project = result.stdout.strip()
        # gcloud returns "(unset)" if no project is configured
        if project and project != "(unset)":
            return project
        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def run_terraform(project_id: str) -> bool:
    """Run Terraform to set up GCP infrastructure"""
    print_header("Setting up GCP Infrastructure with Terraform")
    
    terraform_dir = Path(__file__).parent.parent / "infrastructure" / "terraform"
    
    if not terraform_dir.exists():
        print_error(f"Terraform directory not found: {terraform_dir}")
        return False
    
    try:
        # Initialize Terraform
        print_info("Initializing Terraform...")
        subprocess.run(
            "terraform init",
            cwd=terraform_dir,
            check=True,
            shell=True  # Use shell on Windows
        )
        print_success("Terraform initialized")
        
        # Create terraform.tfvars file
        tfvars_content = f'project_id = "{project_id}"\n'
        tfvars_file = terraform_dir / "terraform.tfvars"
        
        with open(tfvars_file, 'w') as f:
            f.write(tfvars_content)
        
        print_success(f"Created {tfvars_file}")
        
        # Plan
        print_info("Planning infrastructure changes...")
        subprocess.run(
            "terraform plan",
            cwd=terraform_dir,
            check=True,
            shell=True
        )
        
        # Ask for confirmation
        print_warning("\nTerraform will create the following resources:")
        print("  - Service account (cloudguard-agent)")
        print("  - BigQuery datasets (billing_export, cloudguard_audit)")
        print("  - IAM permissions")
        print("  - Enable required APIs")
        
        confirm = input(f"\n{Colors.BOLD}Proceed with Terraform apply? (yes/no): {Colors.ENDC}")
        
        if confirm.lower() != 'yes':
            print_warning("Terraform deployment cancelled")
            return False
        
        # Apply
        print_info("Applying Terraform configuration...")
        result = subprocess.run(
            "terraform apply -auto-approve",
            cwd=terraform_dir,
            check=True,
            capture_output=True,
            text=True,
            shell=True
        )
        
        print_success("Terraform deployment complete!")
        
        # Show outputs
        print_info("\nTerraform Outputs:")
        subprocess.run(
            "terraform output",
            cwd=terraform_dir,
            check=True,
            shell=True
        )
        
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Terraform deployment failed: {e}")
        return False


def configure_billing_export(project_id: str, dataset_name: str):
    """Guide user to configure billing export"""
    print_header("Configure Billing Export")
    
    print(f"""
{Colors.WARNING}⚠ MANUAL STEP REQUIRED{Colors.ENDC}

BigQuery billing export must be configured in the GCP Console:

1. Go to: {Colors.OKBLUE}https://console.cloud.google.com/billing{Colors.ENDC}
2. Select your billing account
3. Click: {Colors.BOLD}Billing Export → BigQuery Export{Colors.ENDC}
4. Click: {Colors.BOLD}Edit Settings{Colors.ENDC}
5. Select:
   - Project: {Colors.OKGREEN}{project_id}{Colors.ENDC}
   - Dataset: {Colors.OKGREEN}{dataset_name}{Colors.ENDC}
6. Click: {Colors.BOLD}Save{Colors.ENDC}

Note: It may take 24 hours for billing data to start flowing.
    """)
    
    input(f"{Colors.BOLD}Press Enter once you've configured billing export...{Colors.ENDC}")
    print_success("Billing export configuration noted")


def get_api_keys() -> Dict[str, str]:
    """Get API keys from user"""
    print_header("API Keys Configuration")
    
    api_keys = {}
    
    # SendGrid
    print(f"""
{Colors.BOLD}━━━ SendGrid Email Setup ━━━{Colors.ENDC}

CloudGuard sends alert emails via SendGrid (free tier: 100 emails/day).

{Colors.BOLD}Step 1: Create a SendGrid account & API key{Colors.ENDC}
  1. Sign up at: {Colors.OKBLUE}https://sendgrid.com/{Colors.ENDC}
  2. Go to: {Colors.BOLD}Settings → API Keys{Colors.ENDC}
  3. Click {Colors.BOLD}"Create API Key"{Colors.ENDC}
  4. Name it "CloudGuard", select {Colors.BOLD}"Restricted Access"{Colors.ENDC}
  5. Enable {Colors.BOLD}"Mail Send → Mail Send"{Colors.ENDC} permission
  6. Click {Colors.BOLD}"Create & View"{Colors.ENDC} and copy the key (starts with SG.)
""")
    
    sendgrid_key = input(f"{Colors.BOLD}Enter SendGrid API key: {Colors.ENDC}").strip()
    api_keys['sendgrid'] = sendgrid_key
    
    if sendgrid_key:
        print_success("SendGrid API key saved")
        
        # Sender verification guide
        print(f"""
{Colors.WARNING}━━━ IMPORTANT: Verify Your Sender Email ━━━{Colors.ENDC}

{Colors.FAIL}SendGrid will REJECT all emails unless you verify a sender address.{Colors.ENDC}
This is required by anti-spam laws (CAN-SPAM / CASL).

{Colors.BOLD}Step 2: Verify your sender email{Colors.ENDC}
  1. Go to: {Colors.OKBLUE}https://app.sendgrid.com/settings/sender_auth/senders{Colors.ENDC}
  2. Click {Colors.BOLD}"Create New Sender"{Colors.ENDC}
  3. Fill in the form:
     ┌─────────────────────┬──────────────────────────────────┐
     │ From Name           │ Your name (e.g., "Anshul Roy")   │
     │ From Email          │ Your email address               │
     │ Reply To            │ Same email address               │
     │ Company Address     │ Any address (shown in footer)    │
     │ City / State / Zip  │ Your location                    │
     │ Country             │ Your country                     │
     │ Nickname            │ "CloudGuard Alerts"              │
     └─────────────────────┴──────────────────────────────────┘
  4. Click {Colors.BOLD}"Create"{Colors.ENDC}
  5. Check your inbox for the verification email from SendGrid
  6. Click the {Colors.BOLD}verification link{Colors.ENDC} in the email

{Colors.WARNING}⚠ The "From Email" here MUST match the ALERT_EMAIL you enter later.{Colors.ENDC}
{Colors.OKCYAN}ℹ Gmail addresses work fine for personal projects.{Colors.ENDC}
""")
        
        input(f"{Colors.BOLD}Press Enter once you've verified your sender email...{Colors.ENDC}")
        print_success("SendGrid sender verification noted")
    else:
        print_warning("SendGrid API key not provided — email alerts will be disabled")
    
    # Gemini
    print(f"\n{Colors.BOLD}Google AI API Key (Gemini) — Optional:{Colors.ENDC}")
    print("  Used for AI-powered cost analysis (can be added later)")
    print(f"  1. Go to: {Colors.OKBLUE}https://aistudio.google.com/apikey{Colors.ENDC}")
    print("  2. Create a new API key")
    
    gemini_key = input(f"\n{Colors.BOLD}Enter Google AI API key (or press Enter to skip): {Colors.ENDC}").strip()
    api_keys['gemini'] = gemini_key
    
    if gemini_key:
        print_success("Gemini API key saved")
    else:
        print_info("Skipped — AI analysis can be configured later")
    
    return api_keys


def get_user_config() -> Dict[str, any]:
    """Get user configuration"""
    print_header("User Configuration")
    
    config = {}
    
    # Email
    email = input(f"{Colors.BOLD}Enter your email for alerts: {Colors.ENDC}").strip()
    config['email'] = email
    
    # Budget
    budget = input(f"{Colors.BOLD}Enter monthly budget limit (USD) [default: 100]: {Colors.ENDC}").strip()
    config['budget'] = float(budget) if budget else 100.0
    
    # Dry run mode
    print(f"\n{Colors.BOLD}Dry Run Mode:{Colors.ENDC}")
    print("  Recommended for first 1-2 weeks")
    print("  Alerts are sent but no resources are modified")
    
    dry_run = input(f"{Colors.BOLD}Enable dry run mode? (yes/no) [default: yes]: {Colors.ENDC}").strip()
    config['dry_run'] = dry_run.lower() != 'no'
    
    return config


def generate_env_file(project_id: str, api_keys: Dict, user_config: Dict):
    """Generate .env file"""
    print_header("Generating Configuration File")
    
    env_content = f"""# CloudGuard AI - Environment Configuration
# Generated by setup wizard

# User Configuration
ALERT_EMAIL={user_config['email']}

# GCP Configuration
GCP_PROJECT_ID={project_id}
GCP_SERVICE_ACCOUNT_JSON=./cloudguard-sa-key.json
BIGQUERY_BILLING_DATASET=billing_export

# API Keys
SENDGRID_API_KEY={api_keys['sendgrid']}
GOOGLE_AI_API_KEY={api_keys['gemini']}

# Budget Configuration
MONTHLY_BUDGET_LIMIT={user_config['budget']}
ALERT_THRESHOLD=0.75
ANOMALY_SENSITIVITY=2.5

# Safety Configuration
BLOCKLIST_TAGS=production,prod,critical
CONFIRMATION_THRESHOLD_USD=100
MAX_ACTIONS_PER_HOUR=3
DRY_RUN_MODE={str(user_config['dry_run']).lower()}

# Advanced Configuration
JWT_EXPIRATION_HOURS=4
ENABLE_QUIET_HOURS=true
QUIET_HOURS_START=22:00
QUIET_HOURS_END=08:00
QUIET_HOURS_TIMEZONE=America/Los_Angeles

# Deployment
JWT_SECRET=
CLOUD_RUN_REGION=us-central1
LOG_LEVEL=INFO
"""
    
    env_file = Path(__file__).parent.parent / ".env"
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print_success(f"Created .env file: {env_file}")
    
    # Generate JWT secret
    import secrets
    jwt_secret = secrets.token_urlsafe(32)
    
    # Append JWT secret
    with open(env_file, 'a') as f:
        f.write(f"\nJWT_SECRET={jwt_secret}\n")
    
    print_success("Generated JWT secret")


def main():
    """Main setup wizard"""
    print(f"""
{Colors.BOLD}{Colors.HEADER}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║            CloudGuard AI Setup Wizard                     ║
║            Autonomous FinOps Agent                        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
    """)
    
    # Check prerequisites
    print_header("Checking Prerequisites")
    
    if not check_gcloud_installed():
        print_error("gcloud CLI not found")
        print_info("Install from: https://cloud.google.com/sdk/docs/install")
        sys.exit(1)
    print_success("gcloud CLI found")
    
    if not check_terraform_installed():
        print_error("Terraform not found")
        print_info("Install from: https://www.terraform.io/downloads")
        sys.exit(1)
    print_success("Terraform found")
    
    # Get GCP project
    current_project = get_gcp_project_id()
    
    if current_project:
        print_success(f"Current GCP project: {current_project}")
        use_current = input(f"{Colors.BOLD}Use this project? (yes/no): {Colors.ENDC}")
        
        if use_current.lower() == 'yes':
            project_id = current_project
        else:
            project_id = input(f"{Colors.BOLD}Enter GCP project ID: {Colors.ENDC}").strip()
    else:
        project_id = input(f"{Colors.BOLD}Enter GCP project ID: {Colors.ENDC}").strip()
    
    if not project_id:
        print_error("Project ID is required")
        sys.exit(1)
    
    # Run Terraform
    if not run_terraform(project_id):
        print_error("Terraform deployment failed")
        sys.exit(1)
    
    # Configure billing export
    configure_billing_export(project_id, "billing_export")
    
    # Get API keys
    api_keys = get_api_keys()
    
    # Get user config
    user_config = get_user_config()
    
    # Generate .env file
    generate_env_file(project_id, api_keys, user_config)
    
    # Final summary
    print_header("Setup Complete! 🎉")
    
    print(f"""
{Colors.OKGREEN}CloudGuard AI is configured and ready!{Colors.ENDC}

{Colors.BOLD}Next steps:{Colors.ENDC}

1. {Colors.BOLD}Install dependencies:{Colors.ENDC}
   pip install -r requirements.txt

2. {Colors.BOLD}Validate setup:{Colors.ENDC}
   python scripts/validate.py

3. {Colors.BOLD}Test locally:{Colors.ENDC}
   python src/watcher/watcher.py

4. {Colors.BOLD}Deploy to Cloud Run (24/7 monitoring):{Colors.ENDC}
   .\\scripts\\deploy.ps1

{Colors.WARNING}Reminders:{Colors.ENDC}
- Dry run mode is {"ENABLED" if user_config['dry_run'] else "DISABLED"}
- Budget limit: ${user_config['budget']}/month
- Billing data may take 24 hours to appear in BigQuery
{Colors.FAIL}- Make sure your SendGrid sender email is VERIFIED before testing emails!{Colors.ENDC}

{Colors.OKBLUE}Documentation: README.md{Colors.ENDC}
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Setup cancelled by user{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        sys.exit(1)

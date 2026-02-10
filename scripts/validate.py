#!/usr/bin/env python3
"""Validation script for CloudGuard AI setup"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config

# Color codes
class Colors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_check(name: str, passed: bool, message: str = ""):
    """Print a check result"""
    status = f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}" if passed else f"{Colors.FAIL}✗ FAIL{Colors.ENDC}"
    print(f"{status} - {name}")
    if message:
        print(f"       {message}")


def check_env_file() -> Tuple[bool, str]:
    """Check if .env file exists"""
    env_file = Path(__file__).parent.parent / ".env"
    
    if not env_file.exists():
        return False, ".env file not found. Run: python scripts/setup.py"
    
    return True, str(env_file)


def check_service_account_key() -> Tuple[bool, str]:
    """Check if service account key exists"""
    key_file = Path(config.GCP_SERVICE_ACCOUNT_JSON)
    
    if not key_file.exists():
        return False, f"Service account key not found: {config.GCP_SERVICE_ACCOUNT_JSON}"
    
    # Check if it's a valid JSON file
    try:
        import json
        with open(key_file, 'r') as f:
            key_data = json.load(f)
        
        if 'type' not in key_data or key_data['type'] != 'service_account':
            return False, "Invalid service account key format"
        
        return True, f"Found: {key_file}"
    except Exception as e:
        return False, f"Invalid JSON: {e}"


def check_bigquery_connection() -> Tuple[bool, str]:
    """Check if can connect to BigQuery"""
    try:
        from google.cloud import bigquery
        
        client = bigquery.Client.from_service_account_json(
            config.GCP_SERVICE_ACCOUNT_JSON
        )
        
        # Try to list datasets
        datasets = list(client.list_datasets())
        
        return True, f"Connected to project: {config.GCP_PROJECT_ID}"
    except Exception as e:
        return False, f"Connection failed: {str(e)[:100]}"


def check_billing_export() -> Tuple[bool, str]:
    """Check if billing export dataset exists"""
    try:
        from google.cloud import bigquery
        
        client = bigquery.Client.from_service_account_json(
            config.GCP_SERVICE_ACCOUNT_JSON
        )
        
        dataset_id = f"{config.GCP_PROJECT_ID}.{config.BIGQUERY_BILLING_DATASET}"
        
        # Try to get the dataset
        dataset = client.get_dataset(dataset_id)
        
        # List tables to check if billing data exists
        tables = list(client.list_tables(dataset))
        
        if not tables:
            return False, f"Dataset exists but no tables found. Billing export may not be configured yet."
        
        billing_tables = [t for t in tables if 'gcp_billing_export' in t.table_id]
        
        if not billing_tables:
            return False, f"No billing export tables found. Check billing export configuration."
        
        return True, f"Found {len(billing_tables)} billing tables"
        
    except Exception as e:
        return False, f"Dataset check failed: {str(e)[:100]}"


def check_api_keys() -> List[Tuple[str, bool, str]]:
    """Check if API keys are configured"""
    checks = []
    
    # SendGrid
    if config.SENDGRID_API_KEY and config.SENDGRID_API_KEY.startswith('SG.'):
        checks.append(("SendGrid API Key", True, "Configured"))
    else:
        checks.append(("SendGrid API Key", False, "Not configured or invalid format"))
    
    # Gemini
    if config.GOOGLE_AI_API_KEY and config.GOOGLE_AI_API_KEY.startswith('AIza'):
        checks.append(("Gemini API Key", True, "Configured"))
    else:
        checks.append(("Gemini API Key", False, "Not configured or invalid format"))
    
    return checks


def check_configuration() -> List[Tuple[str, bool, str]]:
    """Check configuration values"""
    checks = []
    
    # Required fields
    if config.ALERT_EMAIL:
        checks.append(("Alert Email", True, config.ALERT_EMAIL))
    else:
        checks.append(("Alert Email", False, "Not configured"))
    
    if config.GCP_PROJECT_ID:
        checks.append(("GCP Project ID", True, config.GCP_PROJECT_ID))
    else:
        checks.append(("GCP Project ID", False, "Not configured"))
    
    # Budget
    checks.append(("Monthly Budget", True, f"${config.MONTHLY_BUDGET_LIMIT:.2f}"))
    
    # Dry run mode
    if config.DRY_RUN_MODE:
        checks.append(("Dry Run Mode", True, "ENABLED (safe mode)"))
    else:
        checks.append(("Dry Run Mode", True, "DISABLED (will execute actions)"))
    
    return checks


def main():
    """Run all validation checks"""
    print(f"""
{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          CloudGuard AI Validation                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
""")
    
    all_passed = True
    
    # Check 1: .env file
    print(f"\n{Colors.BOLD}1. Configuration Files{Colors.ENDC}")
    passed, message = check_env_file()
    print_check(".env file", passed, message)
    if not passed:
        all_passed = False
        print(f"\n{Colors.FAIL}Setup incomplete. Run: python scripts/setup.py{Colors.ENDC}\n")
        sys.exit(1)
    
    # Check 2: Service account key
    passed, message = check_service_account_key()
    print_check("Service Account Key", passed, message)
    if not passed:
        all_passed = False
    
    # Check 3: Configuration
    print(f"\n{Colors.BOLD}2. Configuration Values{Colors.ENDC}")
    for name, passed, message in check_configuration():
        print_check(name, passed, message)
        if not passed:
            all_passed = False
    
    # Check 4: API Keys
    print(f"\n{Colors.BOLD}3. API Keys{Colors.ENDC}")
    for name, passed, message in check_api_keys():
        print_check(name, passed, message)
        if not passed:
            all_passed = False
    
    # Check 5: GCP Connectivity
    print(f"\n{Colors.BOLD}4. GCP Connectivity{Colors.ENDC}")
    passed, message = check_bigquery_connection()
    print_check("BigQuery Connection", passed, message)
    if not passed:
        all_passed = False
    
    # Check 6: Billing Export
    if passed:  # Only check if connection succeeded
        passed, message = check_billing_export()
        print_check("Billing Export Dataset", passed, message)
        if not passed:
            print(f"       {Colors.WARNING}Note: Billing data may take up to 24 hours to appear{Colors.ENDC}")
    
    # Summary
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    
    if all_passed:
        print(f"""
{Colors.OKGREEN}{Colors.BOLD}✓ All checks passed!{Colors.ENDC}

CloudGuard AI is ready to use.

{Colors.BOLD}Next steps:{Colors.ENDC}
1. Test the watcher: {Colors.BOLD}python src/watcher/watcher.py{Colors.ENDC}
2. If no errors, proceed to Phase 2 (AI Intelligence)
3. Read the docs: {Colors.BOLD}QUICKSTART.md{Colors.ENDC}
        """)
        sys.exit(0)
    else:
        print(f"""
{Colors.FAIL}{Colors.BOLD}✗ Some checks failed{Colors.ENDC}

Please fix the issues above before continuing.

{Colors.WARNING}Common fixes:{Colors.ENDC}
- Missing .env: Run {Colors.BOLD}python scripts/setup.py{Colors.ENDC}
- Service account: Check {Colors.BOLD}cloudguard-sa-key.json{Colors.ENDC} exists
- Billing export: Configure in GCP Console (see QUICKSTART.md)
        """)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Validation cancelled{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Validation error: {e}{Colors.ENDC}")
        sys.exit(1)

"""Configuration management for CloudGuard AI"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """CloudGuard AI configuration"""
    
    # User settings
    ALERT_EMAIL: str = os.getenv("ALERT_EMAIL", "")
    
    # GCP settings
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCP_SERVICE_ACCOUNT_JSON: str = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")
    BIGQUERY_BILLING_DATASET: str = os.getenv("BIGQUERY_BILLING_DATASET", "billing_export")
    
    # API Keys
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    GOOGLE_AI_API_KEY: str = os.getenv("GOOGLE_AI_API_KEY", "")
    
    # Budget settings
    MONTHLY_BUDGET_LIMIT: float = float(os.getenv("MONTHLY_BUDGET_LIMIT", "100"))
    ALERT_THRESHOLD: float = float(os.getenv("ALERT_THRESHOLD", "0.75"))
    ANOMALY_SENSITIVITY: float = float(os.getenv("ANOMALY_SENSITIVITY", "2.5"))
    
    # Safety settings
    BLOCKLIST_TAGS: str = os.getenv("BLOCKLIST_TAGS", "production,prod,critical")
    CONFIRMATION_THRESHOLD_USD: float = float(os.getenv("CONFIRMATION_THRESHOLD_USD", "100"))
    MAX_ACTIONS_PER_HOUR: int = int(os.getenv("MAX_ACTIONS_PER_HOUR", "3"))
    DRY_RUN_MODE: bool = os.getenv("DRY_RUN_MODE", "false").lower() == "true"
    
    # Advanced settings
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "4"))
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    
    # Quiet hours
    ENABLE_QUIET_HOURS: bool = os.getenv("ENABLE_QUIET_HOURS", "true").lower() == "true"
    QUIET_HOURS_START: str = os.getenv("QUIET_HOURS_START", "22:00")
    QUIET_HOURS_END: str = os.getenv("QUIET_HOURS_END", "08:00")
    QUIET_HOURS_TIMEZONE: str = os.getenv("QUIET_HOURS_TIMEZONE", "America/Los_Angeles")
    
    # Deployment
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8080")
    CLOUD_RUN_REGION: str = os.getenv("CLOUD_RUN_REGION", "us-central1")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required_fields = [
            ("GCP_PROJECT_ID", cls.GCP_PROJECT_ID),
        ]
        
        missing = [name for name, value in required_fields if not value]
        
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True
    
    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        """Get a config value by name"""
        return getattr(cls, key, default) or default


# Create config instance
config = Config()

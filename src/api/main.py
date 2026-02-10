"""FastAPI Application for CloudGuard Remediation API"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import jwt

from src.config import config
from src.api.jwt_handler import jwt_handler
from src.api.safety_rules import safety_rules

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="CloudGuard Remediation API",
    description="Secure API for executing cost-saving remediation actions",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "dry_run_mode": config.DRY_RUN_MODE
    }


@app.get("/api/v1/check")
async def run_check():
    """Trigger a watcher check (called by Cloud Scheduler)"""
    try:
        from src.watcher.watcher import CloudGuardWatcher
        
        watcher = CloudGuardWatcher()
        result = watcher.run_check()
        
        return {
            "status": result.get("status", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
            "anomaly_detected": result.get("anomaly_detected", False),
            "current_spend": result.get("details", {}).get("current_spend", 0),
            "details": result.get("details", {})
        }
    except Exception as e:
        logger.error(f"Check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/test-email")
async def test_email():
    """Send a test alert email to verify email configuration"""
    try:
        from src.notifications.email_service import email_service
        
        # Create mock anomaly data for test
        test_anomaly = {
            "is_anomaly": True,
            "severity": "high",
            "deviation_percent": 45.0,
            "baseline": 10.0,
            "current": 14.5,
            "z_score": 2.8
        }
        test_contributors = [
            {"service": "Compute Engine", "sku": "N1 Standard", "cost": 8.50},
            {"service": "Cloud Storage", "sku": "Standard Storage", "cost": 3.20},
            {"service": "BigQuery", "sku": "Analysis", "cost": 1.90},
        ]
        
        success = email_service.send_cost_alert(
            to_email=config.ALERT_EMAIL,
            current_spend=14.50,
            budget_limit=config.MONTHLY_BUDGET_LIMIT,
            anomaly_info=test_anomaly,
            top_contributors=test_contributors,
            resource_id="test-instance-1",
            project_id=config.GCP_PROJECT_ID
        )
        
        return {
            "status": "sent" if success else "failed",
            "to": config.ALERT_EMAIL,
            "message": "Test email sent successfully" if success else "Failed to send - check SendGrid API key"
        }
    except Exception as e:
        logger.error(f"Test email failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/execute/{action}")
async def execute_action(
    action: str,
    token: str = Query(..., description="JWT token authorizing the action"),
    confirm: Optional[bool] = Query(False, description="Confirm high-cost action")
):
    """Execute a remediation action
    
    Actions:
    - stop: Stop the instance
    - snapshot: Create snapshot then stop
    - ignore: Dismiss the alert (no action)
    """
    
    # Validate action type
    valid_actions = ["stop", "snapshot", "ignore"]
    if action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action: {action}. Valid actions: {valid_actions}"
        )
    
    # Validate token
    try:
        payload = jwt_handler.validate_token(token)
    except jwt.ExpiredSignatureError:
        logger.warning("Attempted action with expired token")
        return HTMLResponse(
            content=get_error_page("Token Expired", 
                "This action link has expired. Please wait for the next alert email."),
            status_code=401
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Attempted action with invalid token: {e}")
        return HTMLResponse(
            content=get_error_page("Invalid Token", 
                "This action link is invalid. Please use the link from your alert email."),
            status_code=401
        )
    
    # Extract payload data
    resource_id = payload.get("resource_id")
    project_id = payload.get("project_id", config.GCP_PROJECT_ID)
    resource_type = payload.get("resource_type", "instance")
    user_email = payload.get("user_email", "unknown")
    estimated_savings = payload.get("estimated_savings", 0)
    
    logger.info(f"Executing action={action} on resource={resource_id} by user={user_email}")
    
    # Handle ignore action
    if action == "ignore":
        logger.info(f"Alert ignored for resource {resource_id}")
        return HTMLResponse(
            content=get_success_page("Alert Dismissed", 
                f"You have dismissed the alert for {resource_id}. No action was taken."),
            status_code=200
        )
    
    # For other actions, we need to execute on GCP
    # Import here to avoid circular imports and allow lazy loading
    from src.api.gcp_executor import gcp_executor
    
    # Parse resource_id to get instance name and zone
    # Expected format: "instance-name" or "zones/zone-name/instances/instance-name"
    if "/" in resource_id:
        parts = resource_id.split("/")
        zone = parts[1] if "zones" in resource_id else "us-central1-a"
        instance_name = parts[-1]
    else:
        instance_name = resource_id
        zone = "us-central1-a"  # Default zone
    
    # Execute the action
    if action == "stop":
        success, message, details = gcp_executor.stop_instance(
            instance_name=instance_name,
            zone=zone,
            user_email=user_email
        )
    elif action == "snapshot":
        success, message, details = gcp_executor.snapshot_and_stop(
            instance_name=instance_name,
            zone=zone,
            user_email=user_email
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    
    # Return result
    if success:
        return HTMLResponse(
            content=get_success_page("Action Completed", message),
            status_code=200
        )
    else:
        return HTMLResponse(
            content=get_error_page("Action Failed", message),
            status_code=400
        )


def get_success_page(title: str, message: str) -> str:
    """Generate a success HTML page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title} - CloudGuard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .card {{
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 400px;
            }}
            .icon {{
                font-size: 64px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #10b981;
                margin: 0 0 16px 0;
            }}
            p {{
                color: #666;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h1>{title}</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """


def get_error_page(title: str, message: str) -> str:
    """Generate an error HTML page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title} - CloudGuard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .card {{
                background: white;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 400px;
            }}
            .icon {{
                font-size: 64px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #ef4444;
                margin: 0 0 16px 0;
            }}
            p {{
                color: #666;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">❌</div>
            <h1>{title}</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """


# Entry point for running with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

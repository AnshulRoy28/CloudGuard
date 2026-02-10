"""CloudGuard Watcher - Main orchestration script"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, Optional, Any, List
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import config
from src.data.bigquery_client import BillingDataClient
from src.data.baseline_tracker import BaselineTracker

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cloudguard.log')
    ]
)

logger = logging.getLogger(__name__)


class CloudGuardWatcher:
    """Main watcher service that orchestrates the monitoring pipeline"""
    
    def __init__(self):
        """Initialize CloudGuard Watcher"""
        logger.info("Initializing CloudGuard Watcher...")
        
        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise
        
        # Initialize components
        self.billing_client = BillingDataClient()
        self.baseline_tracker = BaselineTracker()
        
        logger.info("CloudGuard Watcher initialized successfully")
    
    def run_check(self) -> Dict[str, Any]:
        """Run a complete monitoring check
        
        Returns:
            Dict with check results
        """
        logger.info("=" * 60)
        logger.info("CloudGuard Hourly Check Starting")
        logger.info("=" * 60)
        
        check_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
            "anomaly_detected": False,
            "details": {}
        }
        
        try:
            # Step 1: Query billing data
            logger.info("Step 1: Querying BigQuery billing data...")
            current_total = self.billing_client.get_current_month_total()
            top_contributors = self.billing_client.get_top_cost_contributors()
            daily_pattern = self.billing_client.get_daily_spend_pattern()
            
            check_result["details"]["current_spend"] = current_total
            check_result["details"]["top_contributors"] = top_contributors
            
            logger.info(f"Current month-to-date spend: ${current_total:.2f}")
            logger.info(f"Budget limit: ${config.MONTHLY_BUDGET_LIMIT:.2f}")
            
            # Step 2: Update baseline
            logger.info("Step 2: Updating baseline data...")
            self.baseline_tracker.update_baseline(daily_pattern)
            
            # Step 3: Check against budget threshold
            budget_threshold = config.MONTHLY_BUDGET_LIMIT * config.ALERT_THRESHOLD
            
            if current_total > budget_threshold:
                logger.warning(
                    f"Budget threshold exceeded: ${current_total:.2f} > ${budget_threshold:.2f}"
                )
                check_result["details"]["budget_exceeded"] = True
            
            # Step 4: Detect anomalies
            logger.info("Step 3: Running anomaly detection...")
            
            # Get today's spend for anomaly detection
            today_spend = sum(
                item.get("today_cost", 0) 
                for item in self.billing_client.get_month_to_date_costs()
            )
            
            anomaly_result = self.baseline_tracker.detect_anomaly(today_spend)
            check_result["details"]["anomaly"] = anomaly_result
            
            if anomaly_result["is_anomaly"]:
                logger.warning(
                    f"Anomaly detected: ${today_spend:.2f} (baseline: ${anomaly_result['baseline']:.2f}, "
                    f"+{anomaly_result['deviation_percent']:.1f}%, z-score: {anomaly_result['z_score']:.2f})"
                )
                check_result["anomaly_detected"] = True
                
                # Send email notification
                self._send_alert_email(
                    current_spend=current_total,
                    anomaly_info=anomaly_result,
                    top_contributors=top_contributors
                )
            else:
                logger.info(
                    f"No anomaly detected: ${today_spend:.2f} (within {anomaly_result.get('threshold', 'N/A')} std dev)"
                )
            
            logger.info("=" * 60)
            logger.info("CloudGuard Check Complete")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during check: {e}", exc_info=True)
            check_result["status"] = "error"
            check_result["error"] = str(e)
        
        return check_result
    
    def _send_alert_email(
        self,
        current_spend: float,
        anomaly_info: Dict,
        top_contributors: List[Dict]
    ):
        """Send alert email when anomaly is detected
        
        Args:
            current_spend: Current month-to-date spend
            anomaly_info: Anomaly detection results
            top_contributors: List of top cost contributors
        """
        try:
            from src.notifications.email_service import email_service
            
            # Get the top cost contributor as the resource to act on
            resource_id = "unknown"
            if top_contributors:
                top_item = top_contributors[0]
                resource_id = top_item.get("sku", top_item.get("service", "unknown"))
            
            # Send email
            success = email_service.send_cost_alert(
                to_email=config.ALERT_EMAIL,
                current_spend=current_spend,
                budget_limit=config.MONTHLY_BUDGET_LIMIT,
                anomaly_info=anomaly_info,
                top_contributors=top_contributors,
                resource_id=resource_id,
                project_id=config.GCP_PROJECT_ID
            )
            
            if success:
                logger.info(f"Alert email sent to {config.ALERT_EMAIL}")
            else:
                logger.error("Failed to send alert email")
                
        except Exception as e:
            logger.error(f"Error sending alert email: {e}", exc_info=True)


def main():
    """Main entry point"""
    try:
        watcher = CloudGuardWatcher()
        result = watcher.run_check()
        
        # Print summary
        print("\n" + "=" * 60)
        print("CHECK SUMMARY")
        print("=" * 60)
        print(f"Status: {result['status']}")
        print(f"Current Spend: ${result['details'].get('current_spend', 0):.2f}")
        print(f"Anomaly Detected: {result['anomaly_detected']}")
        
        if result.get('details', {}).get('anomaly'):
            anomaly = result['details']['anomaly']
            print(f"Baseline: ${anomaly.get('baseline', 0):.2f}")
            print(f"Deviation: {anomaly.get('deviation_percent', 0):.1f}%")
            print(f"Severity: {anomaly.get('severity', 'unknown')}")
        
        print("=" * 60)
        
        # Exit code based on result
        sys.exit(0 if result['status'] == 'success' else 1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

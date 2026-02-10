"""Email Service for CloudGuard cost alerts"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader

from src.config import config
from src.api.jwt_handler import jwt_handler

logger = logging.getLogger(__name__)


class EmailService:
    """SendGrid email service for cost alerts"""
    
    def __init__(self):
        """Initialize email service"""
        self.api_key = config.SENDGRID_API_KEY
        # Use the alert email as sender (must be verified in SendGrid)
        self.from_email = config.ALERT_EMAIL or "noreply@example.com"
        self.template_dir = Path(__file__).parent.parent.parent / "templates"
        
        # Initialize SendGrid client
        if self.api_key:
            self.client = SendGridAPIClient(self.api_key)
        else:
            logger.warning("SendGrid API key not configured")
            self.client = None
        
        # Initialize Jinja2
        if self.template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir))
            )
        else:
            logger.warning(f"Template directory not found: {self.template_dir}")
            self.jinja_env = None
    
    def generate_action_urls(
        self,
        resource_id: str,
        project_id: str,
        estimated_savings: float,
        user_email: str,
        base_url: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate action URLs with embedded JWT tokens
        
        Args:
            resource_id: Resource identifier
            project_id: GCP project ID
            estimated_savings: Estimated monthly savings
            user_email: Email address receiving the alert
            base_url: API base URL (defaults to config)
        
        Returns:
            Dict with action names as keys and URLs as values
        """
        if not base_url:
            base_url = config.get("API_BASE_URL", "http://localhost:8080")
        
        actions = ["stop", "snapshot", "ignore"]
        urls = {}
        
        for action in actions:
            urls[action] = jwt_handler.generate_action_url(
                base_url=base_url,
                resource_id=resource_id,
                action=action,
                project_id=project_id,
                estimated_savings=estimated_savings,
                user_email=user_email
            )
        
        return urls
    
    def render_alert_email(
        self,
        current_spend: float,
        budget_limit: float,
        anomaly_info: Dict,
        top_contributors: List[Dict],
        action_urls: Dict[str, str]
    ) -> str:
        """Render the alert email HTML
        
        Args:
            current_spend: Current month-to-date spend
            budget_limit: Monthly budget limit
            anomaly_info: Anomaly detection results
            top_contributors: List of top cost contributors
            action_urls: Dict of action URLs
        
        Returns:
            Rendered HTML string
        """
        # Use template if available
        if self.jinja_env:
            try:
                template = self.jinja_env.get_template("alert_email.html")
                return template.render(
                    current_spend=current_spend,
                    budget_limit=budget_limit,
                    budget_percent=(current_spend / budget_limit * 100) if budget_limit > 0 else 0,
                    anomaly=anomaly_info,
                    top_contributors=top_contributors[:5],
                    action_urls=action_urls,
                    timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
                )
            except Exception as e:
                logger.error(f"Error rendering template: {e}")
        
        # Fallback to inline HTML
        return self._render_fallback_email(
            current_spend, budget_limit, anomaly_info, top_contributors, action_urls
        )
    
    def _render_fallback_email(
        self,
        current_spend: float,
        budget_limit: float,
        anomaly_info: Dict,
        top_contributors: List[Dict],
        action_urls: Dict[str, str]
    ) -> str:
        """Render a simple fallback email if template fails"""
        budget_percent = (current_spend / budget_limit * 100) if budget_limit > 0 else 0
        severity = anomaly_info.get("severity", "unknown")
        deviation = anomaly_info.get("deviation_percent", 0)
        
        contributors_html = ""
        for c in top_contributors[:5]:
            contributors_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{c.get('service', 'Unknown')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">${c.get('cost', 0):.2f}</td>
            </tr>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>CloudGuard Cost Alert</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">⚠️ Cost Alert</h1>
                    <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">CloudGuard has detected unusual spending</p>
                </div>
                
                <!-- Cost Summary -->
                <div style="padding: 30px; text-align: center; border-bottom: 1px solid #eee;">
                    <div style="font-size: 48px; font-weight: bold; color: #ef4444;">${current_spend:.2f}</div>
                    <div style="color: #666; margin-top: 8px;">Month-to-Date Spend ({budget_percent:.0f}% of budget)</div>
                    <div style="margin-top: 16px; display: inline-block; background: #fef2f2; color: #ef4444; padding: 8px 16px; border-radius: 20px; font-weight: 500;">
                        {severity.upper()}: +{deviation:.0f}% above baseline
                    </div>
                </div>
                
                <!-- Top Contributors -->
                <div style="padding: 30px;">
                    <h3 style="margin: 0 0 16px 0; color: #333;">Top Cost Contributors</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #f9fafb;">
                                <th style="padding: 12px 8px; text-align: left; font-weight: 600;">Service</th>
                                <th style="padding: 12px 8px; text-align: left; font-weight: 600;">Cost</th>
                            </tr>
                        </thead>
                        <tbody>
                            {contributors_html}
                        </tbody>
                    </table>
                </div>
                
                <!-- Action Buttons -->
                <div style="padding: 30px; background: #f9fafb; text-align: center;">
                    <p style="margin: 0 0 20px 0; color: #666;">Take action on the top cost contributor:</p>
                    
                    <a href="{action_urls.get('stop', '#')}" style="display: inline-block; background: #ef4444; color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 8px; min-width: 120px;">
                        🛑 Stop Instance
                    </a>
                    
                    <a href="{action_urls.get('snapshot', '#')}" style="display: inline-block; background: #3b82f6; color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 8px; min-width: 120px;">
                        📸 Snapshot & Stop
                    </a>
                    
                    <a href="{action_urls.get('ignore', '#')}" style="display: inline-block; background: #6b7280; color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 8px; min-width: 120px;">
                        ✓ Ignore
                    </a>
                </div>
                
                <!-- Footer -->
                <div style="padding: 20px; text-align: center; color: #999; font-size: 12px;">
                    <p>CloudGuard AI • Autonomous FinOps Agent</p>
                    <p>Action links expire in 4 hours</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def send_cost_alert(
        self,
        to_email: str,
        current_spend: float,
        budget_limit: float,
        anomaly_info: Dict,
        top_contributors: List[Dict],
        resource_id: str,
        project_id: str
    ) -> bool:
        """Send a cost alert email
        
        Args:
            to_email: Recipient email address
            current_spend: Current month-to-date spend
            budget_limit: Monthly budget limit
            anomaly_info: Anomaly detection results
            top_contributors: List of top cost contributors
            resource_id: Primary resource to act on
            project_id: GCP project ID
        
        Returns:
            True if email sent successfully
        """
        if not self.client:
            logger.error("SendGrid client not initialized")
            return False
        
        # Generate action URLs
        estimated_savings = anomaly_info.get("current", 0) - anomaly_info.get("baseline", 0)
        action_urls = self.generate_action_urls(
            resource_id=resource_id,
            project_id=project_id,
            estimated_savings=max(0, estimated_savings),
            user_email=to_email
        )
        
        # Render email
        html_content = self.render_alert_email(
            current_spend=current_spend,
            budget_limit=budget_limit,
            anomaly_info=anomaly_info,
            top_contributors=top_contributors,
            action_urls=action_urls
        )
        
        # Create email
        severity = anomaly_info.get("severity", "unknown").upper()
        subject = f"🚨 [{severity}] CloudGuard: Cost anomaly detected (${current_spend:.2f})"
        
        message = Mail(
            from_email=Email(self.from_email, "CloudGuard AI"),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        try:
            response = self.client.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Alert email sent to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return False


# Lazy singleton
_email_service = None

def get_email_service():
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

class _LazyEmailService:
    def __getattr__(self, name):
        return getattr(get_email_service(), name)

email_service = _LazyEmailService()

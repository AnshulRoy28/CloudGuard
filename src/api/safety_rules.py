"""Safety rules for CloudGuard remediation actions"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from src.config import config

logger = logging.getLogger(__name__)


class SafetyRules:
    """Implements safety checks before executing remediation actions"""
    
    def __init__(self):
        """Initialize safety rules"""
        self.blocklist_tags = [t.strip() for t in config.BLOCKLIST_TAGS.split(",")]
        self.confirmation_threshold = config.CONFIRMATION_THRESHOLD_USD
        self.max_actions_per_hour = config.MAX_ACTIONS_PER_HOUR
        self.dry_run = config.DRY_RUN_MODE
        
        # In-memory rate limiting (use Redis in production)
        self._action_history: Dict[str, List[datetime]] = defaultdict(list)
    
    def check_blocklist(self, resource_labels: Dict[str, str]) -> Tuple[bool, str]:
        """Check if resource has blocklisted tags
        
        Args:
            resource_labels: Dict of resource labels/tags
        
        Returns:
            Tuple of (is_blocked, reason)
        """
        for tag in self.blocklist_tags:
            # Check if tag exists as key or value
            if tag.lower() in [k.lower() for k in resource_labels.keys()]:
                return True, f"Resource has blocklisted label: {tag}"
            if tag.lower() in [str(v).lower() for v in resource_labels.values()]:
                return True, f"Resource has blocklisted label value: {tag}"
        
        # Special check for common production indicators
        env_label = resource_labels.get("env", resource_labels.get("environment", ""))
        if env_label.lower() in ["production", "prod"]:
            return True, "Resource is marked as production environment"
        
        return False, ""
    
    def check_rate_limit(self, user_email: str) -> Tuple[bool, str]:
        """Check if user has exceeded rate limit
        
        Args:
            user_email: Email of user performing action
        
        Returns:
            Tuple of (is_rate_limited, reason)
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        self._action_history[user_email] = [
            t for t in self._action_history[user_email]
            if t > one_hour_ago
        ]
        
        # Check limit
        action_count = len(self._action_history[user_email])
        
        if action_count >= self.max_actions_per_hour:
            return True, f"Rate limit exceeded: {action_count}/{self.max_actions_per_hour} actions in the last hour"
        
        return False, ""
    
    def record_action(self, user_email: str):
        """Record that an action was performed
        
        Args:
            user_email: Email of user who performed action
        """
        self._action_history[user_email].append(datetime.utcnow())
    
    def check_high_cost(self, estimated_savings: float) -> Tuple[bool, str]:
        """Check if action involves high-cost resource requiring confirmation
        
        Args:
            estimated_savings: Estimated monthly savings in USD
        
        Returns:
            Tuple of (needs_confirmation, reason)
        """
        if estimated_savings >= self.confirmation_threshold:
            return True, f"High-cost action: ${estimated_savings:.2f}/month requires confirmation"
        
        return False, ""
    
    def validate_action(
        self,
        action: str,
        resource_id: str,
        resource_labels: Dict[str, str],
        user_email: str,
        estimated_savings: float = 0.0
    ) -> Tuple[bool, str, Dict]:
        """Run all safety checks for an action
        
        Args:
            action: Action to perform
            resource_id: Resource ID
            resource_labels: Resource labels/tags
            user_email: User email
            estimated_savings: Estimated monthly savings
        
        Returns:
            Tuple of (is_safe, reason, details)
        """
        details = {
            "dry_run": self.dry_run,
            "checks_passed": [],
            "checks_failed": []
        }
        
        # Check 1: Blocklist
        is_blocked, reason = self.check_blocklist(resource_labels)
        if is_blocked:
            details["checks_failed"].append(("blocklist", reason))
            logger.warning(f"Action blocked: {reason}")
            return False, reason, details
        details["checks_passed"].append("blocklist")
        
        # Check 2: Rate limit
        is_limited, reason = self.check_rate_limit(user_email)
        if is_limited:
            details["checks_failed"].append(("rate_limit", reason))
            logger.warning(f"Action blocked: {reason}")
            return False, reason, details
        details["checks_passed"].append("rate_limit")
        
        # Check 3: High cost (warning only, doesn't block)
        needs_confirmation, reason = self.check_high_cost(estimated_savings)
        if needs_confirmation:
            details["needs_confirmation"] = True
            details["confirmation_reason"] = reason
            logger.info(f"Action needs confirmation: {reason}")
        details["checks_passed"].append("high_cost")
        
        # Check 4: Dry run mode
        if self.dry_run:
            details["dry_run_mode"] = True
            logger.info(f"DRY RUN: Would execute {action} on {resource_id}")
        
        return True, "All safety checks passed", details


# Singleton instance
safety_rules = SafetyRules()

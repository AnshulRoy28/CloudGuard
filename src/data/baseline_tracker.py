"""Baseline tracking for anomaly detection"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import statistics

logger = logging.getLogger(__name__)


class BaselineTracker:
    """Tracks spending baseline and detects anomalies"""
    
    def __init__(self, state_file: str = "baseline_state.json"):
        """Initialize baseline tracker
        
        Args:
            state_file: Path to JSON file storing baseline state
        """
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load baseline state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load baseline state: {e}")
                return {"daily_spend": [], "last_updated": None}
        return {"daily_spend": [], "last_updated": None}
    
    def _save_state(self):
        """Save baseline state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            logger.info(f"Baseline state saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save baseline state: {e}")
    
    def update_baseline(self, daily_spend_data: List[Dict]):
        """Update baseline with new daily spend data
        
        Args:
            daily_spend_data: List of dicts with 'date', 'day_of_week', 'daily_spend'
        """
        self.state["daily_spend"] = daily_spend_data
        self.state["last_updated"] = datetime.utcnow().isoformat()
        self._save_state()
        logger.info(f"Updated baseline with {len(daily_spend_data)} days of data")
    
    def detect_anomaly(self, current_spend: float) -> Dict:
        """Detect if current spend is anomalous vs historical baseline
        
        Args:
            current_spend: Current spending amount to check
        
        Returns:
            Dict with anomaly detection results
        """
        if not self.state.get("daily_spend"):
            logger.warning("No baseline data available for anomaly detection")
            return {
                "is_anomaly": False,
                "severity": "unknown",
                "message": "Insufficient baseline data",
                "baseline": 0,
                "deviation_percent": 0,
                "z_score": 0
            }
        
        # Calculate rolling average and std dev
        daily_spends = [item["daily_spend"] for item in self.state["daily_spend"]]
        
        # Use last 7 days for rolling average
        recent_spends = daily_spends[:7]  # Data is sorted desc by date
        
        if len(recent_spends) < 3:
            logger.warning("Insufficient data for reliable anomaly detection")
            return {
                "is_anomaly": False,
                "severity": "unknown",
                "message": "Need at least 3 days of data",
                "baseline": 0,
                "deviation_percent": 0,
                "z_score": 0
            }
        
        # Calculate statistics
        avg_spend = statistics.mean(recent_spends)
        std_dev = statistics.stdev(recent_spends) if len(recent_spends) > 1 else 0
        
        # Handle edge case: std_dev = 0 (spending is perfectly consistent)
        if std_dev == 0:
            if current_spend > avg_spend:
                z_score = 5.0  # Arbitrary high value to indicate anomaly
            else:
                z_score = 0.0
        else:
            z_score = (current_spend - avg_spend) / std_dev
        
        # Determine if anomalous
        from src.config import config
        threshold = config.ANOMALY_SENSITIVITY  # Default: 2.5 std dev
        
        is_anomaly = z_score > threshold
        
        # Calculate deviation percentage
        deviation_percent = ((current_spend - avg_spend) / avg_spend * 100) if avg_spend > 0 else 0
        
        # Determine severity
        if z_score > 3.0:
            severity = "critical"
        elif z_score > 2.5:
            severity = "high"
        elif z_score > 2.0:
            severity = "medium"
        else:
            severity = "low"
        
        result = {
            "is_anomaly": is_anomaly,
            "severity": severity if is_anomaly else "normal",
            "message": self._get_anomaly_message(is_anomaly, deviation_percent),
            "baseline": round(avg_spend, 2),
            "current": round(current_spend, 2),
            "deviation_percent": round(deviation_percent, 1),
            "z_score": round(z_score, 2),
            "threshold": threshold
        }
        
        logger.info(
            f"Anomaly detection: current=${current_spend:.2f}, "
            f"baseline=${avg_spend:.2f}, z_score={z_score:.2f}, "
            f"anomaly={is_anomaly}"
        )
        
        return result
    
    def get_day_of_week_baseline(self, day_of_week: int) -> Optional[float]:
        """Get average spend for a specific day of week
        
        Args:
            day_of_week: Day of week (1=Sunday, 7=Saturday per BigQuery)
        
        Returns:
            Average spend for that day of week, or None if insufficient data
        """
        if not self.state.get("daily_spend"):
            return None
        
        dow_spends = [
            item["daily_spend"] 
            for item in self.state["daily_spend"]
            if item.get("day_of_week") == day_of_week
        ]
        
        if len(dow_spends) < 2:
            return None
        
        return statistics.mean(dow_spends)
    
    def _get_anomaly_message(self, is_anomaly: bool, deviation_percent: float) -> str:
        """Generate human-readable anomaly message"""
        if not is_anomaly:
            return "Spending is within normal range"
        
        if deviation_percent > 200:
            return f"Spending is {deviation_percent:.0f}% above normal - investigate immediately"
        elif deviation_percent > 100:
            return f"Spending is {deviation_percent:.0f}% above normal - significant anomaly"
        elif deviation_percent > 50:
            return f"Spending is {deviation_percent:.0f}% above normal - moderate anomaly"
        else:
            return f"Spending is {deviation_percent:.0f}% above normal - minor anomaly"

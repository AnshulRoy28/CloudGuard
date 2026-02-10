"""BigQuery client for billing data queries"""

from google.cloud import bigquery
from typing import Dict, List, Any
import logging
from pathlib import Path

from src.config import config

logger = logging.getLogger(__name__)


class BillingDataClient:
    """Client for querying GCP billing data from BigQuery"""
    
    def __init__(self):
        """Initialize BigQuery client"""
        # Use service account key file locally, ADC on Cloud Run
        if config.GCP_SERVICE_ACCOUNT_JSON and Path(config.GCP_SERVICE_ACCOUNT_JSON).exists():
            self.client = bigquery.Client.from_service_account_json(
                config.GCP_SERVICE_ACCOUNT_JSON
            )
        else:
            # Application Default Credentials (Cloud Run attaches SA automatically)
            self.client = bigquery.Client(project=config.GCP_PROJECT_ID)
        self.project_id = config.GCP_PROJECT_ID
        self.dataset = config.BIGQUERY_BILLING_DATASET
        
        # Load SQL queries
        self.queries = self._load_queries()
    
    def _load_queries(self) -> Dict[str, str]:
        """Load SQL queries from file"""
        queries_file = Path(__file__).parent / "queries.sql"
        
        with open(queries_file, 'r') as f:
            content = f.read()
        
        # Parse queries (split by -- Query N:)
        queries = {}
        current_query = []
        current_name = None
        
        for line in content.split('\n'):
            if line.startswith('-- Query'):
                if current_name and current_query:
                    queries[current_name] = '\n'.join(current_query)
                current_name = line.split(':')[1].strip()
                current_query = []
            elif not line.startswith('--') and line.strip():
                current_query.append(line)
        
        # Add last query
        if current_name and current_query:
            queries[current_name] = '\n'.join(current_query)
        
        return queries
    
    def get_month_to_date_costs(self) -> List[Dict[str, Any]]:
        """Get current month-to-date costs by service and SKU"""
        query = self._format_query("Current Month-to-Date Spend by Service")
        
        logger.info("Querying month-to-date costs...")
        query_job = self.client.query(query)
        results = query_job.result()
        
        costs = []
        for row in results:
            costs.append({
                "service_name": row.service_name,
                "sku_name": row.sku_name,
                "total_cost": float(row.total_cost),
                "today_cost": float(row.today_cost),
                "hours_running": int(row.hours_running) if row.hours_running else 0,
                "cost_per_hour": float(row.cost_per_hour) if row.cost_per_hour else 0
            })
        
        logger.info(f"Retrieved {len(costs)} cost line items")
        return costs
    
    def get_daily_spend_pattern(self) -> List[Dict[str, Any]]:
        """Get daily spend pattern for last 30 days (for baseline)"""
        query = self._format_query("Daily Spend Pattern (for baseline tracking)")
        
        logger.info("Querying daily spend pattern...")
        query_job = self.client.query(query)
        results = query_job.result()
        
        daily_spend = []
        for row in results:
            daily_spend.append({
                "date": row.date,
                "day_of_week": int(row.day_of_week),
                "daily_spend": float(row.daily_spend)
            })
        
        logger.info(f"Retrieved {len(daily_spend)} days of spend data")
        return daily_spend
    
    def get_top_cost_contributors(self) -> List[Dict[str, Any]]:
        """Get top 5 cost contributors for current month"""
        query = self._format_query("Top Cost Contributors (Current Month)")
        
        logger.info("Querying top cost contributors...")
        query_job = self.client.query(query)
        results = query_job.result()
        
        contributors = []
        for row in results:
            contributors.append({
                "service_name": row.service_name,
                "total_cost": float(row.total_cost),
                "percentage_of_total": float(row.percentage_of_total)
            })
        
        logger.info(f"Retrieved {len(contributors)} top contributors")
        return contributors
    
    def get_current_month_total(self) -> float:
        """Get total spend for current month"""
        query = f"""
        SELECT SUM(cost) as total
        FROM `{self.project_id}.{self.dataset}.gcp_billing_export_v1_*`
        WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_TRUNC(CURRENT_DATE(), MONTH))
        AND cost > 0
        """
        
        logger.info("Querying current month total spend...")
        query_job = self.client.query(query)
        results = query_job.result()
        
        for row in results:
            total = float(row.total) if row.total else 0.0
            logger.info(f"Current month total: ${total:.2f}")
            return total
        
        return 0.0
    
    def _format_query(self, query_name: str) -> str:
        """Format a query with project ID and dataset"""
        if query_name not in self.queries:
            raise ValueError(f"Query not found: {query_name}")
        
        query = self.queries[query_name]
        return query.format(
            project_id=self.project_id,
            dataset=self.dataset
        )

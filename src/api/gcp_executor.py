"""GCP Resource Executor for CloudGuard remediation actions"""

import logging
from typing import Dict, Optional, Tuple
from pathlib import Path
from google.cloud import compute_v1
from google.api_core import exceptions as gcp_exceptions

from src.config import config
from src.api.safety_rules import safety_rules

logger = logging.getLogger(__name__)


class GCPExecutor:
    """Executes remediation actions on GCP resources"""
    
    def __init__(self):
        """Initialize GCP executor with credentials"""
        self.project_id = config.GCP_PROJECT_ID
        self.dry_run = config.DRY_RUN_MODE
        
        # Initialize clients — use key file locally, ADC on Cloud Run
        try:
            sa_key = config.GCP_SERVICE_ACCOUNT_JSON
            if sa_key and Path(sa_key).exists():
                self.instances_client = compute_v1.InstancesClient.from_service_account_json(sa_key)
                self.snapshots_client = compute_v1.SnapshotsClient.from_service_account_json(sa_key)
                self.disks_client = compute_v1.DisksClient.from_service_account_json(sa_key)
            else:
                # Application Default Credentials (Cloud Run)
                self.instances_client = compute_v1.InstancesClient()
                self.snapshots_client = compute_v1.SnapshotsClient()
                self.disks_client = compute_v1.DisksClient()
            logger.info("GCP clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GCP clients: {e}")
            raise
    
    def get_instance(self, instance_name: str, zone: str) -> Optional[compute_v1.Instance]:
        """Get instance details
        
        Args:
            instance_name: Name of the instance
            zone: GCP zone (e.g., us-central1-a)
        
        Returns:
            Instance object or None if not found
        """
        try:
            instance = self.instances_client.get(
                project=self.project_id,
                zone=zone,
                instance=instance_name
            )
            return instance
        except gcp_exceptions.NotFound:
            logger.error(f"Instance not found: {instance_name} in {zone}")
            return None
        except Exception as e:
            logger.error(f"Error getting instance: {e}")
            return None
    
    def stop_instance(
        self,
        instance_name: str,
        zone: str,
        user_email: str
    ) -> Tuple[bool, str, Dict]:
        """Stop a Compute Engine instance
        
        Args:
            instance_name: Name of the instance to stop
            zone: GCP zone
            user_email: Email of user performing action
        
        Returns:
            Tuple of (success, message, details)
        """
        details = {
            "action": "stop_instance",
            "instance": instance_name,
            "zone": zone,
            "project": self.project_id
        }
        
        # Get instance details for safety checks
        instance = self.get_instance(instance_name, zone)
        if not instance:
            return False, f"Instance not found: {instance_name}", details
        
        # Get labels for safety check
        labels = dict(instance.labels) if instance.labels else {}
        
        # Run safety checks
        is_safe, reason, safety_details = safety_rules.validate_action(
            action="stop",
            resource_id=instance_name,
            resource_labels=labels,
            user_email=user_email
        )
        
        details["safety_checks"] = safety_details
        
        if not is_safe:
            return False, reason, details
        
        # Check if already stopped
        if instance.status == "TERMINATED":
            return True, "Instance is already stopped", details
        
        # Execute action (or dry run)
        if self.dry_run:
            details["dry_run"] = True
            logger.info(f"DRY RUN: Would stop instance {instance_name}")
            return True, f"DRY RUN: Would stop instance {instance_name}", details
        
        try:
            operation = self.instances_client.stop(
                project=self.project_id,
                zone=zone,
                instance=instance_name
            )
            
            # Wait for operation to complete
            operation.result()
            
            # Record action for rate limiting
            safety_rules.record_action(user_email)
            
            details["operation_id"] = operation.name
            logger.info(f"Successfully stopped instance: {instance_name}")
            
            return True, f"Instance {instance_name} stopped successfully", details
            
        except Exception as e:
            logger.error(f"Failed to stop instance: {e}")
            return False, f"Failed to stop instance: {str(e)}", details
    
    def create_snapshot(
        self,
        disk_name: str,
        zone: str,
        snapshot_name: Optional[str] = None
    ) -> Tuple[bool, str, Dict]:
        """Create a snapshot of a disk
        
        Args:
            disk_name: Name of the disk to snapshot
            zone: GCP zone
            snapshot_name: Optional custom snapshot name
        
        Returns:
            Tuple of (success, message, details)
        """
        from datetime import datetime
        
        if not snapshot_name:
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            snapshot_name = f"cloudguard-{disk_name}-{timestamp}"
        
        details = {
            "action": "create_snapshot",
            "disk": disk_name,
            "snapshot_name": snapshot_name,
            "zone": zone,
            "project": self.project_id
        }
        
        if self.dry_run:
            details["dry_run"] = True
            logger.info(f"DRY RUN: Would create snapshot {snapshot_name}")
            return True, f"DRY RUN: Would create snapshot {snapshot_name}", details
        
        try:
            # Get the disk
            disk = self.disks_client.get(
                project=self.project_id,
                zone=zone,
                disk=disk_name
            )
            
            # Create snapshot
            snapshot = compute_v1.Snapshot(
                name=snapshot_name,
                source_disk=disk.self_link,
                description=f"CloudGuard automatic snapshot of {disk_name}"
            )
            
            operation = self.snapshots_client.insert(
                project=self.project_id,
                snapshot_resource=snapshot
            )
            
            # Wait for operation
            operation.result()
            
            details["operation_id"] = operation.name
            logger.info(f"Successfully created snapshot: {snapshot_name}")
            
            return True, f"Snapshot {snapshot_name} created successfully", details
            
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return False, f"Failed to create snapshot: {str(e)}", details
    
    def snapshot_and_stop(
        self,
        instance_name: str,
        zone: str,
        user_email: str
    ) -> Tuple[bool, str, Dict]:
        """Create snapshots of all instance disks, then stop the instance
        
        Args:
            instance_name: Name of the instance
            zone: GCP zone
            user_email: Email of user performing action
        
        Returns:
            Tuple of (success, message, details)
        """
        details = {
            "action": "snapshot_and_stop",
            "instance": instance_name,
            "zone": zone,
            "snapshots": []
        }
        
        # Get instance
        instance = self.get_instance(instance_name, zone)
        if not instance:
            return False, f"Instance not found: {instance_name}", details
        
        # Create snapshots for each disk
        for disk in instance.disks:
            disk_name = disk.source.split("/")[-1]
            success, message, snap_details = self.create_snapshot(disk_name, zone)
            
            details["snapshots"].append({
                "disk": disk_name,
                "success": success,
                "message": message
            })
            
            if not success:
                return False, f"Failed to snapshot disk {disk_name}: {message}", details
        
        # Now stop the instance
        success, message, stop_details = self.stop_instance(instance_name, zone, user_email)
        details["stop_result"] = stop_details
        
        if success:
            return True, f"Snapshots created and instance {instance_name} stopped", details
        else:
            return False, f"Snapshots created but failed to stop: {message}", details


# Lazy singleton — only created when first accessed
_gcp_executor = None

def get_gcp_executor():
    global _gcp_executor
    if _gcp_executor is None:
        _gcp_executor = GCPExecutor()
    return _gcp_executor

# For backward compatibility
class _LazyExecutor:
    def __getattr__(self, name):
        return getattr(get_gcp_executor(), name)

gcp_executor = _LazyExecutor()

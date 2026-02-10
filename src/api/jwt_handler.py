"""JWT Token Handler for CloudGuard remediation actions"""

import jwt
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import secrets

from src.config import config

logger = logging.getLogger(__name__)


class JWTHandler:
    """Handles JWT token generation and validation for secure remediation actions"""
    
    def __init__(self):
        """Initialize JWT handler with secret from config"""
        self.secret = config.JWT_SECRET
        self.algorithm = "HS256"
        self.expiry_hours = config.JWT_EXPIRATION_HOURS
        
        if not self.secret:
            # Generate a secret if not configured (for development)
            logger.warning("JWT_SECRET not configured, generating temporary secret")
            self.secret = secrets.token_urlsafe(32)
    
    def generate_token(
        self,
        resource_id: str,
        action: str,
        project_id: str,
        resource_type: str = "instance",
        estimated_savings: float = 0.0,
        user_email: Optional[str] = None
    ) -> str:
        """Generate a JWT token for a remediation action
        
        Args:
            resource_id: ID of the resource to act on
            action: Action to perform (stop, snapshot, ignore)
            project_id: GCP project ID
            resource_type: Type of resource (instance, disk, bucket)
            estimated_savings: Estimated monthly savings in USD
            user_email: Email of user who will receive the alert
        
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expiry = now + timedelta(hours=self.expiry_hours)
        
        payload = {
            # Standard claims
            "iat": now,
            "exp": expiry,
            "jti": secrets.token_urlsafe(16),  # Unique token ID
            
            # Custom claims
            "resource_id": resource_id,
            "action": action,
            "project_id": project_id,
            "resource_type": resource_type,
            "estimated_savings": estimated_savings,
            "user_email": user_email,
            
            # For audit logging
            "issued_at": now.isoformat(),
        }
        
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        
        logger.info(
            f"Generated token for action={action} on resource={resource_id}, "
            f"expires in {self.expiry_hours} hours"
        )
        
        return token
    
    def validate_token(self, token: str) -> Dict:
        """Validate and decode a JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload dict
        
        Raises:
            jwt.ExpiredSignatureError: Token has expired
            jwt.InvalidTokenError: Token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm]
            )
            
            logger.info(
                f"Token validated: action={payload.get('action')} "
                f"resource={payload.get('resource_id')}"
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token validation failed: expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token validation failed: {e}")
            raise
    
    def generate_action_url(
        self,
        base_url: str,
        resource_id: str,
        action: str,
        project_id: str,
        **kwargs
    ) -> str:
        """Generate a complete action URL with embedded token
        
        Args:
            base_url: Base URL of the API (e.g., https://api.example.com)
            resource_id: Resource ID
            action: Action to perform
            project_id: GCP project ID
            **kwargs: Additional token payload fields
        
        Returns:
            Complete URL with token parameter
        """
        token = self.generate_token(
            resource_id=resource_id,
            action=action,
            project_id=project_id,
            **kwargs
        )
        
        # URL encode the token
        from urllib.parse import urlencode
        params = urlencode({"token": token})
        
        url = f"{base_url}/api/v1/execute/{action}?{params}"
        
        return url


# Singleton instance
jwt_handler = JWTHandler()

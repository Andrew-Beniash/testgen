"""
Security utilities for authentication and authorization.

This module provides JWT token handling, password hashing,
and security dependencies for the API.
"""

from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"
security = HTTPBearer()


def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Token expiration time
        
    Returns:
        str: Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    
    logger.debug("Access token created", subject=str(subject), expires=expire)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        Optional[str]: The subject (user ID) if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        subject: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if subject is None or token_type != "access":
            return None
            
        return subject
    except JWTError as e:
        logger.warning("Token verification failed", error=str(e))
        return None


def get_password_hash(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Get the current authenticated user.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        str: User ID
        
    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        raise credentials_exception
    
    user_id = verify_token(credentials.credentials)
    if user_id is None:
        raise credentials_exception
        
    return user_id


def create_webhook_signature(payload: str, secret: str) -> str:
    """
    Create HMAC signature for webhook validation.
    
    Args:
        payload: Webhook payload
        secret: Webhook secret
        
    Returns:
        str: HMAC signature
    """
    import hmac
    import hashlib
    
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"sha256={signature}"


def verify_webhook_signature(
    payload: str, signature: str, secret: str
) -> bool:
    """
    Verify webhook signature.
    
    Args:
        payload: Webhook payload
        signature: Provided signature
        secret: Webhook secret
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    expected_signature = create_webhook_signature(payload, secret)
    return hmac.compare_digest(signature, expected_signature)

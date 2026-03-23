"""
Centralized configuration management for WhatsApp Reminder Bot.

This module provides validated access to all environment variables,
ensuring proper formatting and failing fast on misconfiguration.
"""

import os
import secrets
import warnings
from dataclasses import dataclass
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def _generate_fallback_secret() -> str:
    """Generate a cryptographically secure fallback secret for development."""
    return secrets.token_hex(32)


@dataclass(frozen=True)
class TwilioConfig:
    """Twilio API configuration with validation."""
    account_sid: str
    auth_token: str
    whatsapp_from: str
    
    def __post_init__(self):
        """Validate configuration after creation."""
        if not self.account_sid.startswith("AC") or len(self.account_sid) != 34:
            raise ValueError(
                f"Invalid TWILIO_ACCOUNT_SID format. Expected 34 characters starting with 'AC', "
                f"got {len(self.account_sid)} characters."
            )
        
        if len(self.auth_token) != 32:
            raise ValueError(
                f"Invalid TWILIO_AUTH_TOKEN format. Expected 32 characters, "
                f"got {len(self.auth_token)}."
            )
        
        if not self.whatsapp_from.startswith("whatsapp:+"):
            raise ValueError(
                f"Invalid TWILIO_WHATSAPP_FROM format. Expected 'whatsapp:+<number>', "
                f"got '{self.whatsapp_from}'."
            )


@dataclass(frozen=True)
class FlaskConfig:
    """Flask application configuration."""
    secret_key: str
    env: str
    debug: bool
    
    def __post_init__(self):
        """Warn about weak secrets in production."""
        if len(self.secret_key) < 32 and self.env == "production":
            warnings.warn(
                "SECRET_KEY is shorter than 32 characters. "
                "Use a stronger key in production: python -c \"import secrets; print(secrets.token_hex(32))\"",
                RuntimeWarning,
                stacklevel=2
            )


@dataclass(frozen=True)
class AppConfig:
    """Application-wide configuration container."""
    twilio: TwilioConfig
    flask: FlaskConfig
    database_path: Path
    log_level: str
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.flask.env == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.flask.env == "production"


def load_config() -> AppConfig:
    """
    Load and validate all configuration from environment variables.
    
    Raises:
        RuntimeError: If required configuration is missing or invalid.
    
    Returns:
        Fully validated AppConfig instance.
    """
    # Collect missing required variables
    missing = []
    
    # Twilio configuration
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    if not account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not auth_token:
        missing.append("TWILIO_AUTH_TOKEN")
    
    whatsapp_from = os.environ.get("TWILIO_WHATSAPP_FROM")
    if not whatsapp_from:
        missing.append("TWILIO_WHATSAPP_FROM")
    
    # Flask configuration
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        # In development, generate a random key automatically
        if os.environ.get("FLASK_ENV", "development") == "development":
            secret_key = _generate_fallback_secret()
            warnings.warn(
                "SECRET_KEY not set. Using auto-generated key for development. "
                "Set SECRET_KEY in .env for persistent sessions.",
                UserWarning,
                stacklevel=2
            )
        else:
            missing.append("SECRET_KEY")
    
    # Fail fast if required variables are missing
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Please copy .env.example to .env and configure all required values."
        )
    
    # Build configuration objects (validation happens in __post_init__)
    try:
        twilio_config = TwilioConfig(
            account_sid=account_sid,
            auth_token=auth_token,
            whatsapp_from=whatsapp_from
        )
    except ValueError as e:
        raise RuntimeError(f"Invalid Twilio configuration: {e}")
    
    flask_config = FlaskConfig(
        secret_key=secret_key,
        env=os.environ.get("FLASK_ENV", "development"),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    )
    
    return AppConfig(
        twilio=twilio_config,
        flask=flask_config,
        database_path=Path(os.environ.get("DATABASE_PATH", "reminders.db")),
        log_level=os.environ.get("LOG_LEVEL", "DEBUG" if flask_config.debug else "INFO")
    )


# Singleton instance for application-wide use
# Import this in other modules: from config import CONFIG
CONFIG = load_config()

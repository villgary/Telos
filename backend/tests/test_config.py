import os
import pytest
from pydantic import ValidationError

def test_database_url_required():
    """DATABASE_URL must be set or raise ValidationError."""
    from backend.config import Settings
    # Clear env
    original = os.environ.get("DATABASE_URL")
    if original:
        del os.environ["DATABASE_URL"]
    try:
        with pytest.raises(ValidationError):
            Settings()
    finally:
        if original:
            os.environ["DATABASE_URL"] = original

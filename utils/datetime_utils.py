# utils/datetime_utils.py
from datetime import datetime
from typing import Union, Optional

def safe_datetime_parse(value: Union[str, datetime, None]) -> Optional[datetime]:
    """Safely parse datetime from either string or datetime object
    
    This utility handles the transition from SQLite (which stores datetimes as strings)
    to PostgreSQL (which returns datetime objects directly).
    
    Args:
        value: A datetime string, datetime object, or None
        
    Returns:
        datetime object or None if value is None or invalid
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            # Handle timezone info if present
            if value.endswith('Z'):
                value = value.replace('Z', '+00:00')
            result = datetime.fromisoformat(value)
            # Remove timezone info to maintain compatibility with existing code
            if result.tzinfo is not None:
                result = result.replace(tzinfo=None)
            return result
        except ValueError:
            # Try alternative parsing if fromisoformat fails
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    return None
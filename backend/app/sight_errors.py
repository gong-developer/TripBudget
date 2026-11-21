from fastapi import HTTPException


class NoSights(HTTPException):
    """Successful provider lookup with no usable sights or regional boundary."""

# app/utils/request_utils.py
from fastapi import Request

def get_client_ip(request: Request) -> str:
    """دریافت IP واقعی کلاینت (حتی اگر پشت پروکسی باشد)"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def get_user_agent(request: Request) -> str:
    """دریافت User Agent مرورگر یا کلاینت"""
    return request.headers.get("User-Agent", "unknown")
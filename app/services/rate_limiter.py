from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _get_key(request: Request) -> str:
    # RapidAPI proxies all traffic — use their user header when present
    return (
        request.headers.get("X-RapidAPI-User")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or get_remote_address(request)
    )


limiter = Limiter(
    key_func=_get_key,
    default_limits=["200/minute"],
)


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return a structured 429 response when a rate limit is hit."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": (
                "You have exceeded the allowed request rate for this endpoint. "
                "Please wait before making additional requests."
            ),
            "detail": f"Limit: {exc.limit.limit}",
            "retry_after": "See the Retry-After response header.",
            "upgrade_url": "https://rapidapi.com/resileon/api/resileon-api",
        },
        headers={"Retry-After": "60"},
    )

import time
from collections import defaultdict
from fastapi import HTTPException


class LoginRateLimiter:
    """Simple in-memory rate limiter for login endpoints.
    Records every attempt and rejects if max_attempts exceeded within window."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check_and_record(self, ip: str):
        now = time.time()
        cutoff = now - self.window_seconds
        self._attempts[ip] = [t for t in self._attempts[ip] if t > cutoff]
        if len(self._attempts[ip]) >= self.max_attempts:
            retry_after = int(self._attempts[ip][0] + self.window_seconds - now)
            raise HTTPException(
                status_code=429,
                detail=f"Demasiados intentos. Intenta de nuevo en {retry_after} segundos.",
                headers={"Retry-After": str(retry_after)},
            )
        self._attempts[ip].append(now)


_login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)

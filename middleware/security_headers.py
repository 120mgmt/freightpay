# File: middleware/security_headers.py
# Purpose: Enterprise HTTP Security Headers Middleware
# Status: Enterprise Hardened (OWASP ASVS + SaaS Production)
# Date: 2026-02-26

from __future__ import annotations

from flask import Flask, Response


def apply_security_headers(app: Flask) -> None:
    @app.after_request
    def set_headers(response: Response) -> Response:
        # Prevent MIME sniffing
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Clickjacking protection
        response.headers.setdefault("X-Frame-Options", "DENY")

        # XSS protection (legacy but safe)
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")

        # Strict Transport Security (HTTPS only)
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )

        # Referrer control
        response.headers.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin",
        )

        # Permissions policy (disable dangerous APIs)
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )

        # Content Security Policy — locked down for SaaS
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "img-src 'self' data: https:; "
                "script-src 'self' https://js.stripe.com; "
                "style-src 'self' 'unsafe-inline'; "
                "frame-src https://js.stripe.com https://hooks.stripe.com; "
                "connect-src 'self' https://api.stripe.com; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none';"
            ),
        )

        return response


__all__ = ["apply_security_headers"]

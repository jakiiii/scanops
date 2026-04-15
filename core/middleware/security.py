import base64
import re
import secrets

from django.conf import settings


SCRIPT_TAG_PATTERN = re.compile(r"<script\b(?![^>]*\bnonce=)([^>]*)>", re.IGNORECASE)
STYLE_TAG_PATTERN = re.compile(r"<style\b(?![^>]*\bnonce=)([^>]*)>", re.IGNORECASE)
HEAD_TAG_PATTERN = re.compile(r"<head(\s*[^>]*)>", re.IGNORECASE)


class SecurityHeadersMiddleware:
    """Add security headers and a nonce-based CSP to every response."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.infrastructure_headers = {
            "Forwarded",
            "Server",
            "Via",
            "X-Backend-Server",
            "X-Forwarded-For",
            "X-Powered-By",
            "X-Real-IP",
            "X-Served-By",
            "X-Upstream",
        }

    def __call__(self, request):
        request.csp_nonce = self._generate_nonce()
        response = self.get_response(request)

        if self._is_html_response(response):
            response = self._apply_nonce_markup(response, request.csp_nonce)

        if getattr(settings, "SECURE_HSTS_SECONDS", 0):
            include_sub = getattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
            preload = getattr(settings, "SECURE_HSTS_PRELOAD", False)
            hsts = f"max-age={settings.SECURE_HSTS_SECONDS}"
            if include_sub:
                hsts += "; includeSubDomains"
            if preload:
                hsts += "; preload"
            response.headers["Strict-Transport-Security"] = hsts

        response.headers["Content-Security-Policy"] = self._build_csp_header(request.csp_nonce)
        response.headers.setdefault("X-Frame-Options", getattr(settings, "X_FRAME_OPTIONS", "DENY"))
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Referrer-Policy",
            getattr(settings, "SECURE_REFERRER_POLICY", "same-origin"),
        )
        response.headers.setdefault(
            "Permissions-Policy",
            getattr(settings, "PERMISSIONS_POLICY", "geolocation=(self), camera=(), microphone=()"),
        )

        for header in self.infrastructure_headers:
            response.headers.pop(header, None)

        return response

    @staticmethod
    def _generate_nonce():
        token = secrets.token_bytes(16)
        return base64.b64encode(token).decode("ascii").rstrip("=")

    @staticmethod
    def _is_html_response(response):
        if getattr(response, "streaming", False):
            return False
        content_type = response.headers.get("Content-Type", "")
        return "text/html" in content_type

    def _apply_nonce_markup(self, response, nonce):
        charset = response.charset or "utf-8"
        content = response.content.decode(charset)
        content = SCRIPT_TAG_PATTERN.sub(rf'<script nonce="{nonce}"\1>', content)
        content = STYLE_TAG_PATTERN.sub(rf'<style nonce="{nonce}"\1>', content)

        if 'name="csp-nonce"' not in content:
            content = HEAD_TAG_PATTERN.sub(
                rf'<head\1><meta name="csp-nonce" content="{nonce}">',
                content,
                count=1,
            )

        response.content = content.encode(charset)
        response.headers.pop("Content-Length", None)
        return response

    def _build_csp_header(self, nonce):
        configured_policy = getattr(settings, "CONTENT_SECURITY_POLICY", None)

        if isinstance(configured_policy, str) and configured_policy.strip():
            return configured_policy

        policy = dict(configured_policy or {})
        script_sources = list(policy.get("script-src", ("'self'",)))
        script_nonce = f"'nonce-{nonce}'"
        if script_nonce not in script_sources:
            script_sources.insert(1, script_nonce)
        policy["script-src"] = tuple(script_sources)

        directives = []
        for directive, sources in policy.items():
            if not sources:
                continue
            if isinstance(sources, str):
                value = sources
            else:
                value = " ".join(dict.fromkeys(sources))
            directives.append(f"{directive} {value}")
        return "; ".join(directives)

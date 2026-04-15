import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger("exceptions_log")


class SafeExceptionMiddleware(MiddlewareMixin):
    """Convert unhandled exceptions into safe user-facing responses."""

    json_messages = {
        400: "The request could not be processed.",
        403: "You do not have permission to perform this action.",
        404: "The requested resource was not found.",
        405: "The requested method is not allowed for this resource.",
        500: "An unexpected error occurred. Please try again later.",
    }
    template_names = {
        400: "errors/400.html",
        403: "errors/403.html",
        404: "errors/404.html",
        405: "errors/405.html",
        500: "errors/500.html",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, exception):
        if isinstance(exception, Http404):
            return self._build_response(request, status=404)
        if isinstance(exception, PermissionDenied):
            return self._build_response(request, status=403)
        if isinstance(exception, SuspiciousOperation):
            logger.warning(
                "Suspicious request rejected: %s %s",
                request.method,
                request.path,
                exc_info=True,
            )
            return self._build_response(request, status=400)
        logger.exception(
            "Unhandled application error for %s %s",
            request.method,
            request.path,
            extra={
                "request_path": request.path,
                "request_method": request.method,
                "user_id": getattr(getattr(request, "user", None), "pk", None),
            },
        )
        return self._build_response(request, status=500)

    def process_response(self, request, response):
        content_type = response.headers.get("Content-Type", "")
        if (
            getattr(response, "streaming", False)
            or response.status_code == 200
        ):
            return response

        if response.status_code == 405:
            return self._copy_safe_headers(response, self._build_response(request, status=405))

        if (
            settings.DEBUG
            and response.status_code in self.template_names
            and "text/html" in content_type
        ):
            return self._copy_safe_headers(
                response,
                self._build_response(request, status=response.status_code),
            )
        return response

    def _build_response(self, request, *, status):
        if self._expects_json(request):
            return JsonResponse({"detail": self.json_messages[status]}, status=status)
        return render(request, self.template_names[status], status=status)

    @staticmethod
    def _copy_safe_headers(source_response, target_response):
        for header_name in ("Allow",):
            if header_name in source_response.headers:
                target_response.headers[header_name] = source_response.headers[header_name]
        return target_response

    @staticmethod
    def _expects_json(request):
        accept_header = request.headers.get("Accept", "")
        requested_with = request.headers.get("X-Requested-With", "")
        content_type = request.headers.get("Content-Type", "")
        return (
            requested_with == "XMLHttpRequest"
            or "application/json" in accept_header
            or "application/json" in content_type
            or request.path.startswith("/api/")
            or "/ajax/" in request.path
        )

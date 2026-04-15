from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token


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


@requires_csrf_token
def bad_request(request, exception, template_name="errors/400.html"):
    return render(request, template_name, status=400)


@requires_csrf_token
def permission_denied(request, exception, template_name="errors/403.html"):
    return render(request, template_name, status=403)


@requires_csrf_token
def page_not_found(request, exception, template_name="errors/404.html"):
    return render(request, template_name, status=404)


@requires_csrf_token
def server_error(request, template_name="errors/500.html"):
    return render(request, template_name, status=500)


@requires_csrf_token
def csrf_failure(request, reason="", template_name="errors/403.html"):
    if _expects_json(request):
        return JsonResponse({"detail": "You do not have permission to perform this action."}, status=403)
    return render(request, template_name, status=403)

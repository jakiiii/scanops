from datetime import timedelta
from ipware import get_client_ip
from django.shortcuts import render
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.timezone import now

from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import AccessMixin


class AdministratorRequiredMixin(AccessMixin):
    """Verify that the current user is a staff user."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_administrator:
            return redirect(reverse_lazy('accounts:permission_denied'))
        return super().dispatch(request, *args, **kwargs)


class OperatorRequiredMixin(AccessMixin):
    """Verify that the current user is an operator user."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not getattr(request.user, 'is_operator', False):
            return redirect(reverse_lazy('accounts:permission_denied'))
        return super().dispatch(request, *args, **kwargs)


class AuthorRequiredMixin(AccessMixin):
    """Verify that the current user is a staff user."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Use boolean 'or' and guard attributes to avoid unexpected behavior
        is_admin = getattr(request.user, 'is_administrator', False)
        is_operator = getattr(request.user, 'is_operator', False)
        if not (is_admin or is_operator):
            return redirect(reverse_lazy('accounts:permission_denied'))
        return super().dispatch(request, *args, **kwargs)


class OwnedObjectMixin:
    owner_field = "posted_by"

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self.request.user, 'is_administrator', False):
            return queryset
        return queryset.filter(**{self.owner_field: self.request.user})


class RateLimitMixin:
    # Set default rate limit: 5 requests per hour
    max_requests = 5
    rate_limit_period = timedelta(hours=1)
    cache_prefix = "rate_limit"

    def get_cache_key(self):
        """
        Generate a unique cache key for the user or IP address.
        Override this method if you want custom cache key logic.
        """
        if self.request.user.is_authenticated:
            return f"{self.cache_prefix}_user_{self.request.user.pk}"
        else:
            ip_address, _ = get_client_ip(self.request)
            return f"{self.cache_prefix}_ip_{ip_address}"

    def has_exceeded_rate_limit(self):
        """
        Check if the request count has exceeded the rate limit.
        """
        cache_key = self.get_cache_key()
        request_times = cache.get(cache_key, [])

        # Filter out requests that are older than the rate limit period
        recent_requests = [req_time for req_time in request_times if now() - req_time < self.rate_limit_period]

        # Update the cache with filtered request times
        cache.set(cache_key, recent_requests, timeout=int(self.rate_limit_period.total_seconds()))

        # Return True if the number of requests has exceeded the max_requests
        return len(recent_requests) >= self.max_requests

    def add_request_to_cache(self):
        """
        Add the current request timestamp to the cache.
        """
        cache_key = self.get_cache_key()
        request_times = cache.get(cache_key, [])
        request_times.append(now())
        cache.set(cache_key, request_times, timeout=int(self.rate_limit_period.total_seconds()))

    def dispatch(self, request, *args, **kwargs):
        """
        Override the dispatch method to check rate limit before proceeding.
        """
        if self.has_exceeded_rate_limit():
            # Rate limit exceeded, show an error message or return a custom response
            messages.error(request, "You have exceeded the maximum number of allowed requests. Please try again later.")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
            return render(request, 'rate_limit_error.html', status=429)

        # Add the current request to the cache
        self.add_request_to_cache()

        # Proceed with the normal dispatch if rate limit is not exceeded
        return super().dispatch(request, *args, **kwargs)

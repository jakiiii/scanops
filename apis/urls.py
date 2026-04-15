from functools import wraps

from django.conf import settings
from django.urls import path, include, re_path
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def administrator_required_view(view):
    @wraps(view)
    @login_required
    def wrapped(request, *args, **kwargs):
        if not getattr(request.user, 'is_administrator', False):
            return redirect('accounts:permission_denied')
        return view(request, *args, **kwargs)

    return wrapped

urlpatterns = [
    # Phase 1 web apps
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.dashboard.urls', namespace='dashboard')),
    path('targets/', include('apps.targets.urls', namespace='targets')),
    path('scans/', include('apps.scans.urls', namespace='scans')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('schedules/', include('apps.schedules.urls', namespace='schedules')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('assets/', include('apps.assets.urls', namespace='assets')),
    path('ops/', include('apps.ops.urls', namespace='ops')),


    # tinymce
    path('tinymce/', include('tinymce.urls')),
]

if 'drf_yasg' in settings.INSTALLED_APPS:
    from drf_yasg import openapi
    from drf_yasg.views import get_schema_view

    schema_view = get_schema_view(
       openapi.Info(
          title="Snippets API",
          default_version='v1',
          description="Test description",
          terms_of_service="https://www.google.com/policies/terms/",
          contact=openapi.Contact(email="contact@snippets.local"),
          license=openapi.License(name="BSD License"),
       ),
       public=False,
    )

    urlpatterns += [
        re_path(
            r'^swagger(?P<format>\.json|\.yaml)$',
            administrator_required_view(schema_view.without_ui(cache_timeout=0)),
            name='schema-json'
        ),
        re_path(
            r'^swagger/$',
            administrator_required_view(schema_view.with_ui('swagger', cache_timeout=0)),
            name='schema-swagger-ui'
        ),
        re_path(
            r'^redoc/$',
            administrator_required_view(schema_view.with_ui('redoc', cache_timeout=0)),
            name='schema-redoc'
        ),
    ]

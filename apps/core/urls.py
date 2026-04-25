from django.urls import path

from apps.core.views import DocumentationView


app_name = "core"


urlpatterns = [
    path("documentation/", DocumentationView.as_view(), name="documentation"),
]

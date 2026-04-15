from django.urls import path

from apps.targets.views import TargetCreateView, TargetDetailView, TargetListView

app_name = "targets"


urlpatterns = [
    path("", TargetListView.as_view(), name="list"),
    path("new/", TargetCreateView.as_view(), name="create"),
    path("<int:pk>/", TargetDetailView.as_view(), name="detail"),
]

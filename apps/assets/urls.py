from django.urls import path

from apps.assets.views import (
    AssetChangeHistoryView,
    AssetChangesPartialView,
    AssetDetailView,
    AssetListView,
    AssetSyncView,
)

app_name = "assets"


urlpatterns = [
    path("", AssetListView.as_view(), name="list"),
    path("sync/", AssetSyncView.as_view(), name="sync"),
    path("changes/", AssetChangeHistoryView.as_view(), name="changes"),
    path("<int:pk>/", AssetDetailView.as_view(), name="detail"),
    path("<int:pk>/changes/", AssetChangeHistoryView.as_view(), name="detail-changes"),
    path("<int:pk>/changes/partial/", AssetChangesPartialView.as_view(), name="changes-partial"),
]


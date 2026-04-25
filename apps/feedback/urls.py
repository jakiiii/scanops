from django.urls import path

from apps.feedback.views import IssueCreateView, SuggestionCreateView


app_name = "feedback"


urlpatterns = [
    path("suggestions/", SuggestionCreateView.as_view(), name="suggestion"),
    path("issues/", IssueCreateView.as_view(), name="issue"),
]


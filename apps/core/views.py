from __future__ import annotations

from django.views.generic import TemplateView

from apps.core.services.documentation_service import build_documentation_payload


class DocumentationView(TemplateView):
    template_name = "documentation/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [{"label": "Read Documentation", "url": ""}]
        context.update(build_documentation_payload())
        return context

from django.core.exceptions import PermissionDenied


class BaseSearchService:
    def __init__(self, request, search_query):
        self.request = request
        self.search_query = search_query

    def get_organizations(self):
        """
        Returns the list of organizations that the user can access based on their role.
        """
        if self.request.user.is_staff:
            selected_org = self.request.query_params.get('organization')
            if selected_org:
                return [selected_org]
            return [self.request.user.organization.id]
        else:
            # Non-staff users can only view their own organization's data
            if 'organization' in self.request.query_params:
                raise PermissionDenied("You are not allowed to filter by organization.")
            return [self.request.user.organization.id]

    def get_queryset(self):
        """
        This method needs to be overridden in child classes to return the specific queryset.
        """
        raise NotImplementedError("Subclasses must implement the 'get_queryset' method.")

    def search(self):
        """
        Generic search method that applies filtering and common logic.
        """
        organizations = self.get_organizations()

        queryset = self.get_queryset().exclude(
            status=self.model.StatusChoices.ARCHIVED
        ).filter(
            self.get_search_filter(),
            organizations__in=organizations,
            status=self.model.StatusChoices.PUBLISHED
        ).order_by(*self.get_ordering())

        return queryset

    def get_search_filter(self):
        """
        This method should return the filter logic based on the search query.
        """
        raise NotImplementedError("Subclasses must implement the 'get_search_filter' method.")

    def get_ordering(self):
        """
        This method returns the ordering criteria for the queryset.
        """
        return ['-source_publish_date', 'name']  # Default ordering


class OrganizationService:
    def __init__(self, request):
        self.request = request

    def get_organizations(self):
        """
        Returns the list of organizations that the user can access based on their role.
        """
        if self.request.user.is_staff:
            selected_org = self.request.query_params.get('organization')
            if selected_org:
                return [selected_org]
            return [self.request.user.organization.id]
        else:
            # Non-staff users can only view their own organization's data
            if 'organization' in self.request.query_params:
                raise PermissionDenied("You are not allowed to filter by organization.")
            return [self.request.user.organization.id]

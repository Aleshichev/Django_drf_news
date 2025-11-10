from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Permission class to allow only authors of a comment to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Permissions are allowed to read-only requests
        if request.method in permissions.SAFE_METHODS:
            return True
        #Permission to edit only to the author
        return obj.author == request.user
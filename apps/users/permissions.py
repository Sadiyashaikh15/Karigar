from rest_framework.permissions import BasePermission


class IsProvider(BasePermission):
    message = "Only providers can do this."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role == "provider")


class IsCustomer(BasePermission):
    message = "Only customers can do this."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role == "customer")

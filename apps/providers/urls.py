from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryListView, MyAvailabilityViewSet, MyProfileView, MyServiceViewSet,
    MyTimeOffViewSet, ProviderDetailView, ProviderSearchView, ProviderSlotsView,
)

router = DefaultRouter()
router.register("me/services", MyServiceViewSet, basename="my-services")
router.register("me/availability", MyAvailabilityViewSet, basename="my-availability")
router.register("me/timeoff", MyTimeOffViewSet, basename="my-timeoff")

urlpatterns = [
    path("categories/", CategoryListView.as_view()),
    path("providers/", ProviderSearchView.as_view()),
    path("providers/<int:pk>/", ProviderDetailView.as_view()),
    path("providers/<int:pk>/slots/", ProviderSlotsView.as_view()),
    path("me/profile/", MyProfileView.as_view()),
    path("", include(router.urls)),
]

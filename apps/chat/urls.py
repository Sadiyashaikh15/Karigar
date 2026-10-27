from django.urls import path

from .views import MessageHistoryView

urlpatterns = [path("<int:booking_id>/messages/", MessageHistoryView.as_view())]

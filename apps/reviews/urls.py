from django.urls import path

from .views import ReportReviewView, ReviewListCreateView

urlpatterns = [
    path("", ReviewListCreateView.as_view()),
    path("<int:pk>/report/", ReportReviewView.as_view()),
]

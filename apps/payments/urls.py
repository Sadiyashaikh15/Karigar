from django.urls import path

from .views import CreateOrderView, PaymentStatusView, VerifyPaymentView, WebhookView

urlpatterns = [
    path("create-order/", CreateOrderView.as_view()),
    path("verify/", VerifyPaymentView.as_view()),
    path("webhook/", WebhookView.as_view()),
    path("status/<int:booking_id>/", PaymentStatusView.as_view()),
]

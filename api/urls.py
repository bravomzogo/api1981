from django.urls import path
from .views import ServiceListView, BookDeliveryView, TrackParcelView, PricingView, AreasView

urlpatterns = [
    path('services/', ServiceListView.as_view(), name='services'),
    path('book/', BookDeliveryView.as_view(), name='book'),
    path('track/<str:tracking_number>/', TrackParcelView.as_view(), name='track'),
    path('pricing/', PricingView.as_view(), name='pricing'),
    path('areas/', AreasView.as_view(), name='areas'),
]
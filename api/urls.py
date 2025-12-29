# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    ServiceListView, BookDeliveryView, TrackParcelView,
    PricingView, AreasView, ParcelViewSet, DriverViewSet,
    DashboardView, UserProfileView, ApprovalListView,
    StatisticsView, LocationUpdateView, DriverDashboardView,
    TrackingHistoryView, UserParcelsView, DriverLocationView,
    CustomTokenObtainPairView, RegisterView, register_user,
    health_check,DriverGPSTrackingView, DriverStatusUpdateView, 
    DriverRouteTrackingView, DriverLocationHistoryView
)

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'parcels', ParcelViewSet, basename='parcel')
router.register(r'drivers', DriverViewSet, basename='driver')

urlpatterns = [
    # Health check
    path('health/', health_check, name='health-check'),
    
    # Your existing endpoints
    path('services/', ServiceListView.as_view(), name='services'),
    path('book/', BookDeliveryView.as_view(), name='book'),
    path('track/<str:tracking_number>/', TrackParcelView.as_view(), name='track'),
    path('pricing/', PricingView.as_view(), name='pricing'),
    path('areas/', AreasView.as_view(), name='areas'),
    
    # API endpoints (for React frontend)
    path('', include(router.urls)),
    
    # Authentication - Public endpoints
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/register/', RegisterView.as_view(), name='register'),  # Use RegisterView class
    # OR use the function-based version:
    # path('auth/register/', register_user, name='register'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Protected endpoints (require authentication)
    path('auth/profile/', UserProfileView.as_view({'get': 'retrieve', 'put': 'update'}), name='profile'),
    
    # Dashboard and statistics
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/statistics/', StatisticsView.as_view(), name='statistics'),
    path('user/parcels/', UserParcelsView.as_view(), name='user-parcels'),
    
    # Approval workflow
    path('approvals/', ApprovalListView.as_view(), name='approval-list'),
    path('approvals/pending/', ParcelViewSet.as_view({'get': 'pending_approval'}), name='pending-approvals'),
    path('parcels/<int:pk>/approve/', ParcelViewSet.as_view({'post': 'approve'}), name='approve-parcel'),
    
    # Driver functionality
    path('driver/dashboard/', DriverDashboardView.as_view(), name='driver-dashboard'),
    path('driver/location/update/', DriverViewSet.as_view({'post': 'update_location'}), name='update-location'),
    path('driver/parcels/', DriverViewSet.as_view({'get': 'assigned_parcels'}), name='driver-parcels'),
    path('driver/status/', DriverViewSet.as_view({'get': 'status'}), name='driver-status'),
    
    # Real-time tracking
    path('location/update/', LocationUpdateView.as_view(), name='location-update'),
    path('tracking/<str:tracking_number>/history/', TrackingHistoryView.as_view(), name='tracking-history'),
    path('driver/location/<int:driver_id>/', DriverLocationView.as_view(), name='driver-location-detail'),
    
    # Additional parcel endpoints
    path('parcels/track/<str:tracking_number>/', ParcelViewSet.as_view({'get': 'public_tracking'}), name='public-tracking'),
    
    # For mobile app
    path('mobile/location/update/', LocationUpdateView.as_view(), name='mobile-location-update'),

    # GPS Tracking Endpoints (for mobile apps)
    path('driver/gps/tracking/', DriverGPSTrackingView.as_view(), name='gps-tracking'),
    path('driver/gps/status/', DriverStatusUpdateView.as_view(), name='gps-status'),
    path('driver/gps/route/<int:parcel_id>/', DriverRouteTrackingView.as_view(), name='gps-route'),
    path('driver/location/history/<int:driver_id>/', DriverLocationHistoryView.as_view(), name='driver-location-history'),
]
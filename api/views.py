# api/views.py
from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action, permission_classes, api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
import datetime
from decimal import Decimal
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.authtoken.models import Token
from rest_framework import serializers

from .models import Service, Parcel, Driver, LocationHistory, TrackingEvent, ApprovalLog
from .serializers import (
    ServiceSerializer, ParcelSerializer, ParcelCreateSerializer,
    ParcelApprovalSerializer, DriverSerializer, DriverLocationSerializer,
    UserSerializer, UserCreateSerializer, LocationHistorySerializer,
    TrackingEventSerializer, ApprovalLogSerializer, BookDeliverySerializer,
    PricingSerializer, AreaSerializer, StatisticsSerializer,
    UserProfileSerializer,
)




from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Driver


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Allows login with either username OR email.
    Accepts fields: 'username' (optional), 'email' (optional), 'password' (required)
    At least one of username or email must be provided.
    """

    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove default username field (we're overriding it)
        self.fields.pop('username', None)
        # We'll use our own username and email fields above

    def validate(self, attrs):
        username = attrs.get('username')
        email = attrs.get('email')
        password = attrs.get('password')

        if not password:
            raise serializers.ValidationError({'detail': 'Password is required.'})

        if not username and not email:
            raise serializers.ValidationError({
                'detail': 'You must provide either username or email.'
            })

        # Try to find the user
        user = None
        if email:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                pass
            except User.MultipleObjectsReturned:
                # Rare case: multiple users with same email (should be prevented at registration)
                user = User.objects.filter(email__iexact=email).first()

        if not user and username:
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                pass

        if not user:
            raise serializers.ValidationError({
                'detail': 'No account found with the provided credentials.'
            })

        if not user.is_active:
            raise serializers.ValidationError({
                'detail': 'This account has been deactivated.'
            })

        # Authenticate using username (Django's authenticate expects username)
        authenticated_user = authenticate(
            request=self.context.get('request'),
            username=user.username,
            password=password
        )

        if not authenticated_user:
            raise serializers.ValidationError({
                'detail': 'Invalid password.'
            })

        # Use the authenticated user
        self.user = authenticated_user

        # Generate tokens
        refresh = RefreshToken.for_user(self.user)

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'first_name': self.user.first_name,
                'last_name': self.user.last_name,
                'is_staff': self.user.is_staff,
                'is_superuser': self.user.is_superuser,
            }
        }

        # Add driver info if exists
        try:
            driver = Driver.objects.get(user=self.user)
            data['user']['is_driver'] = True
            data['user']['driver_id'] = driver.id
            data['user']['role'] = 'driver'
        except Driver.DoesNotExist:
            data['user']['is_driver'] = False
            data['user']['role'] = 'admin' if self.user.is_staff else 'user'

        return data



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# Register View with AllowAny permission
class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserCreateSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            
            # Send welcome email
            subject = "Welcome to I&M Courier!"
            message = f"""
Dear {user.first_name or user.username},

Welcome to I&M Courier! Your account has been created successfully.

You can now:
- Book parcel deliveries
- Track your parcels in real-time
- View your delivery history
- Manage your profile

If you have any questions, please contact our support team.

Thank you for choosing I&M Courier!

Best regards,
I&M Courier General Supplier
"""
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Alternative register_user function with AllowAny decorator
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    serializer = UserCreateSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        
        # Send welcome email
        subject = "Welcome to I&M Courier!"
        message = f"""
Dear {user.first_name or user.username},

Welcome to I&M Courier! Your account has been created successfully.

You can now:
- Book parcel deliveries
- Track your parcels in real-time
- View your delivery history
- Manage your profile

If you have any questions, please contact our support team.

Thank you for choosing I&M Courier!

Best regards,
I&M Courier General Supplier
"""
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Permission classes
class IsAdminOrApprover(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and (
            request.user.is_staff or 
            request.user.has_perm('api.can_approve_parcel')
        )

class IsDriverUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and hasattr(request.user, 'driver_profile')

class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        # For Parcel objects
        if hasattr(obj, 'sender_email'):
            return obj.sender_email == request.user.email or obj.receiver_email == request.user.email
        
        # For User objects
        if isinstance(obj, User):
            return obj == request.user
        
        return False

# Existing views (updated)
class ServiceListView(generics.ListAPIView):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]

class BookDeliveryView(generics.CreateAPIView):
    serializer_class = BookDeliverySerializer
    permission_classes = [permissions.AllowAny]  # Allow anyone to book
    
    def perform_create(self, serializer):
        parcel = serializer.save()
        
        # Send confirmation email
        subject = f"I&M Courier - Parcel Request Submitted: {parcel.tracking_number}"
        message = f"""
Dear {parcel.sender_name},

Thank you for submitting your parcel request to I&M Courier!

Your request is now pending approval. We will review it and notify you once it's approved.

Tracking Number: {parcel.tracking_number}
Sender: {parcel.sender_name}
Receiver: {parcel.receiver_name}
Pickup: {parcel.pickup_location}
Delivery: {parcel.delivery_location}
Weight: {parcel.weight} kg

You will receive another email once your request is approved.

Thank you for choosing I&M Courier!

Best regards,
I&M Courier General Supplier
"""
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[parcel.sender_email],
            fail_silently=True,
        )

class TrackParcelView(generics.RetrieveAPIView):
    serializer_class = ParcelSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'tracking_number'
    lookup_url_kwarg = 'tracking_number'
    
    def get_queryset(self):
        return Parcel.objects.all()
    
    def get_object(self):
        tracking_number = self.kwargs.get('tracking_number', '').upper()
        try:
            parcel = Parcel.objects.get(tracking_number=tracking_number)
            return parcel
        except Parcel.DoesNotExist:
            return None
    
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance is None:
                return Response(
                    {'error': 'Parcel not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            serializer = self.get_serializer(instance)
            
            # Get tracking history
            tracking_events = TrackingEvent.objects.filter(parcel=instance)
            location_history = LocationHistory.objects.filter(parcel=instance)[:10]
            
            response_data = {
                'parcel': serializer.data,
                'tracking_events': TrackingEventSerializer(tracking_events, many=True).data,
                'location_history': LocationHistorySerializer(location_history, many=True).data,
                'current_location': {
                    'latitude': float(instance.current_location_lat) if instance.current_location_lat else None,
                    'longitude': float(instance.current_location_lng) if instance.current_location_lng else None,
                }
            }
            
            # Check if parcel is approved
            if instance.approval_status != 'approved':
                response_data['warning'] = 'Parcel not yet approved'
                response_data['approval_status'] = instance.approval_status
                response_data['message'] = 'Your parcel is still pending approval. You will receive an email once approved.'
            
            return Response(response_data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class PricingView(generics.ListAPIView):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = PricingSerializer
    permission_classes = [permissions.AllowAny]

class AreasView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, *args, **kwargs):
        areas = [
            {'name': 'Dar es Salaam', 'code': 'DAR', 'delivery_time': '1-2 days'},
            {'name': 'Arusha', 'code': 'AR', 'delivery_time': '2-3 days'},
            {'name': 'Mwanza', 'code': 'MW', 'delivery_time': '3-4 days'},
            {'name': 'Dodoma', 'code': 'DO', 'delivery_time': '2-3 days'},
            {'name': 'Mbeya', 'code': 'MB', 'delivery_time': '3-4 days'},
            {'name': 'Zanzibar', 'code': 'ZN', 'delivery_time': '2-3 days'},
            {'name': 'Tanga', 'code': 'TN', 'delivery_time': '2-3 days'},
            {'name': 'Morogoro', 'code': 'MO', 'delivery_time': '2-3 days'},
            {'name': 'Kigoma', 'code': 'KG', 'delivery_time': '4-5 days'},
            {'name': 'Mtwara', 'code': 'MT', 'delivery_time': '3-4 days'},
        ]
        return Response(areas)

# New ViewSets
class ParcelViewSet(viewsets.ModelViewSet):
    serializer_class = ParcelSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if not user.is_authenticated:
            return Parcel.objects.none()
        
        if user.is_staff or user.has_perm('api.can_approve_parcel'):
            return Parcel.objects.all().order_by('-created_at')
        
        # Regular users see only their parcels
        return Parcel.objects.filter(
            Q(sender_email=user.email) | 
            Q(receiver_email=user.email)
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ParcelCreateSerializer
        elif self.action == 'approve':
            return ParcelApprovalSerializer
        return ParcelSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'create']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['approve', 'pending_approval']:
            permission_classes = [IsAdminOrApprover]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        parcels = Parcel.objects.filter(approval_status='pending')
        serializer = self.get_serializer(parcels, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        parcel = self.get_object()
        serializer = ParcelApprovalSerializer(data=request.data)
        
        if serializer.is_valid():
            action_type = serializer.validated_data['action']
            notes = serializer.validated_data.get('notes', '')
            
            if action_type == 'approve':
                parcel.approval_status = 'approved'
                parcel.status = 'Approved'
                parcel.approved_by = request.user
                parcel.approved_at = timezone.now()
                
                if 'estimated_delivery' in serializer.validated_data:
                    parcel.estimated_delivery = serializer.validated_data['estimated_delivery']
                
                if 'assigned_driver_id' in serializer.validated_data:
                    try:
                        driver = Driver.objects.get(id=serializer.validated_data['assigned_driver_id'])
                        parcel.assigned_driver = driver
                    except Driver.DoesNotExist:
                        pass
                
                parcel.save()
                
                # Create tracking event
                TrackingEvent.objects.create(
                    parcel=parcel,
                    status='Approved',
                    description=f'Parcel approved by {request.user.get_full_name()}. {notes}',
                    created_by=request.user
                )
                
                # Create approval log
                ApprovalLog.objects.create(
                    parcel=parcel,
                    action='APPROVED',
                    performed_by=request.user,
                    notes=notes
                )
                
                return Response({
                    'message': 'Parcel approved successfully',
                    'tracking_number': parcel.tracking_number
                })
            
            elif action_type == 'reject':
                parcel.approval_status = 'rejected'
                parcel.status = 'Rejected'
                parcel.rejection_reason = serializer.validated_data.get('rejection_reason', '')
                parcel.save()
                
                # Create tracking event
                TrackingEvent.objects.create(
                    parcel=parcel,
                    status='Rejected',
                    description=f'Parcel rejected. Reason: {parcel.rejection_reason}',
                    created_by=request.user
                )
                
                # Create approval log
                ApprovalLog.objects.create(
                    parcel=parcel,
                    action='REJECTED',
                    performed_by=request.user,
                    notes=notes
                )
                
                return Response({'message': 'Parcel rejected successfully'})
            
            elif action_type == 'request_changes':
                parcel.approval_status = 'under_review'
                parcel.save()
                
                # Create tracking event
                TrackingEvent.objects.create(
                    parcel=parcel,
                    status='Under_Review',
                    description=f'Changes requested: {notes}',
                    created_by=request.user
                )
                
                # Create approval log
                ApprovalLog.objects.create(
                    parcel=parcel,
                    action='REQUESTED_CHANGES',
                    performed_by=request.user,
                    notes=notes
                )
                
                return Response({'message': 'Changes requested successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def track(self, request):
        tracking_number = request.data.get('tracking_number')
        if not tracking_number:
            return Response(
                {'error': 'Tracking number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            parcel = Parcel.objects.get(tracking_number=tracking_number.upper())
        except Parcel.DoesNotExist:
            return Response(
                {'error': 'Invalid tracking number'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if parcel.approval_status != 'approved':
            return Response({
                'error': 'Parcel not yet approved',
                'status': parcel.approval_status,
                'tracking_number': parcel.tracking_number,
                'message': 'Your parcel is still pending approval. You will receive an email once approved.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(parcel)
        tracking_events = TrackingEvent.objects.filter(parcel=parcel)
        location_history = LocationHistory.objects.filter(parcel=parcel)[:10]
        
        response_data = {
            'parcel': serializer.data,
            'tracking_events': TrackingEventSerializer(tracking_events, many=True).data,
            'location_history': LocationHistorySerializer(location_history, many=True).data,
            'current_location': {
                'latitude': float(parcel.current_location_lat) if parcel.current_location_lat else None,
                'longitude': float(parcel.current_location_lng) if parcel.current_location_lng else None,
            }
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'], url_path='track/(?P<tracking_number>[^/.]+)')
    def public_tracking(self, request, tracking_number=None):
        return self.track(request)

class DriverViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def update_location(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
        except Driver.DoesNotExist:
            return Response(
                {'error': 'You are not registered as a driver'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DriverLocationSerializer(data=request.data)
        
        if serializer.is_valid():
            lat = serializer.validated_data['latitude']
            lng = serializer.validated_data['longitude']
            address = serializer.validated_data.get('address', '')
            parcel_id = serializer.validated_data.get('parcel_id')
            
            # Update driver location
            driver.current_location_lat = lat
            driver.current_location_lng = lng
            driver.last_location_update = timezone.now()
            driver.save()
            
            # Update specific parcel or all assigned parcels
            if parcel_id:
                try:
                    parcel = Parcel.objects.get(id=parcel_id, assigned_driver=driver)
                    parcel.current_location_lat = lat
                    parcel.current_location_lng = lng
                    parcel.save()
                    
                    # Record location history
                    LocationHistory.objects.create(
                        parcel=parcel,
                        latitude=lat,
                        longitude=lng,
                        address=address,
                        status=parcel.status
                    )
                except Parcel.DoesNotExist:
                    pass
            else:
                # Update all assigned parcels
                assigned_parcels = Parcel.objects.filter(
                    assigned_driver=driver,
                    approval_status='approved',
                    status__in=['Assigned', 'Picked_Up', 'In_Transit', 'Out_for_Delivery']
                )
                
                for parcel in assigned_parcels:
                    parcel.current_location_lat = lat
                    parcel.current_location_lng = lng
                    parcel.save()
                    
                    # Record location history
                    LocationHistory.objects.create(
                        parcel=parcel,
                        latitude=lat,
                        longitude=lng,
                        address=address,
                        status=parcel.status
                    )
            
            return Response({'message': 'Location updated successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def assigned_parcels(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
        except Driver.DoesNotExist:
            return Response(
                {'error': 'You are not registered as a driver'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        parcels = Parcel.objects.filter(
            assigned_driver=driver,
            approval_status='approved'
        )
        serializer = ParcelSerializer(parcels, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
            return Response({
                'is_available': driver.is_available,
                'current_location': {
                    'lat': driver.current_location_lat,
                    'lng': driver.current_location_lng
                },
                'last_update': driver.last_location_update
            })
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )

# Additional API Views
class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.is_staff or user.has_perm('api.can_approve_parcel'):
            # Admin/Approver dashboard
            total_parcels = Parcel.objects.count()
            pending_approval = Parcel.objects.filter(approval_status='pending').count()
            approved_parcels = Parcel.objects.filter(approval_status='approved').count()
            delivered_parcels = Parcel.objects.filter(status='Delivered').count()
            in_transit = Parcel.objects.filter(status='In_Transit').count()
            
            return Response({
                'total_parcels': total_parcels,
                'pending_approval': pending_approval,
                'approved_parcels': approved_parcels,
                'delivered_parcels': delivered_parcels,
                'in_transit_parcels': in_transit,
                'role': 'admin'
            })
        else:
            # User dashboard
            user_parcels = Parcel.objects.filter(
                Q(sender_email=user.email) | 
                Q(receiver_email=user.email)
            )
            
            return Response({
                'total_parcels': user_parcels.count(),
                'pending_approval': user_parcels.filter(approval_status='pending').count(),
                'approved_parcels': user_parcels.filter(approval_status='approved').count(),
                'delivered_parcels': user_parcels.filter(status='Delivered').count(),
                'in_transit_parcels': user_parcels.filter(status='In_Transit').count(),
                'role': 'user'
            })

class UserProfileView(viewsets.ViewSet):
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def retrieve(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    def update(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def create(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            
            # Send welcome email
            subject = "Welcome to I&M Courier!"
            message = f"""
Dear {user.first_name or user.username},

Welcome to I&M Courier! Your account has been created successfully.

You can now:
- Book parcel deliveries
- Track your parcels in real-time
- View your delivery history
- Manage your profile

If you have any questions, please contact our support team.

Thank you for choosing I&M Courier!

Best regards,
I&M Courier General Supplier
"""
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ApprovalListView(generics.ListAPIView):
    permission_classes = [IsAdminOrApprover]
    serializer_class = ParcelSerializer
    
    def get_queryset(self):
        return Parcel.objects.filter(approval_status='pending').order_by('-created_at')

class StatisticsView(APIView):
    permission_classes = [IsAdminOrApprover]
    
    def get(self, request):
        # Get statistics for the last 30 days
        thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
        
        stats = {
            'total_parcels': Parcel.objects.count(),
            'parcels_last_30_days': Parcel.objects.filter(created_at__gte=thirty_days_ago).count(),
            'delivered_parcels': Parcel.objects.filter(status='Delivered').count(),
            'in_transit_parcels': Parcel.objects.filter(status='In_Transit').count(),
            'pending_approval': Parcel.objects.filter(approval_status='pending').count(),
            'total_drivers': Driver.objects.count(),
            'active_drivers': Driver.objects.filter(is_available=True).count(),
            'revenue_last_30_days': self.calculate_revenue(),
        }
        
        return Response(stats)
    
    def calculate_revenue(self):
        thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
        parcels = Parcel.objects.filter(
            created_at__gte=thirty_days_ago,
            approval_status='approved'
        )
        
        revenue = Decimal('0.00')
        for parcel in parcels:
            if parcel.service and parcel.weight:
                revenue += parcel.service.price_per_kg * Decimal(str(parcel.weight))
        
        return revenue

class LocationUpdateView(APIView):
    permission_classes = [IsDriverUser]
    
    def post(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
            serializer = DriverLocationSerializer(data=request.data)
            
            if serializer.is_valid():
                lat = serializer.validated_data['latitude']
                lng = serializer.validated_data['longitude']
                address = serializer.validated_data.get('address', '')
                
                driver.current_location_lat = lat
                driver.current_location_lng = lng
                driver.last_location_update = timezone.now()
                driver.save()
                
                return Response({'message': 'Location updated successfully'})
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class DriverDashboardView(APIView):
    permission_classes = [IsDriverUser]
    
    def get(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
            
            assigned_parcels = Parcel.objects.filter(
                assigned_driver=driver,
                approval_status='approved'
            )
            
            today_deliveries = assigned_parcels.filter(
                estimated_delivery__date=timezone.now().date()
            )
            
            completed_today = assigned_parcels.filter(
                status='Delivered',
                delivery_time__date=timezone.now().date()
            )
            
            return Response({
                'driver_info': DriverSerializer(driver).data,
                'assigned_parcels_count': assigned_parcels.count(),
                'today_deliveries_count': today_deliveries.count(),
                'completed_today_count': completed_today.count(),
                'is_available': driver.is_available,
                'location': {
                    'lat': driver.current_location_lat,
                    'lng': driver.current_location_lng
                }
            })
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class TrackingHistoryView(generics.ListAPIView):
    serializer_class = TrackingEventSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        tracking_number = self.kwargs['tracking_number'].upper()
        try:
            parcel = Parcel.objects.get(tracking_number=tracking_number)
            return TrackingEvent.objects.filter(parcel=parcel).order_by('-timestamp')
        except Parcel.DoesNotExist:
            return TrackingEvent.objects.none()

class UserParcelsView(generics.ListAPIView):
    serializer_class = ParcelSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Parcel.objects.filter(
            Q(sender_email=user.email) | 
            Q(receiver_email=user.email)
        ).order_by('-created_at')

class DriverLocationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, driver_id=None):
        try:
            if driver_id:
                driver = Driver.objects.get(id=driver_id)
            else:
                driver = Driver.objects.get(user=request.user)
            
            return Response({
                'latitude': driver.current_location_lat,
                'longitude': driver.current_location_lng,
                'last_update': driver.last_location_update,
                'is_available': driver.is_available
            })
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )

# Health check endpoint
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    return Response({'status': 'healthy', 'timestamp': timezone.now()})




# api/views.py - Add these new views
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import json

class DriverGPSTrackingView(APIView):
    """
    Main endpoint for automatic GPS location updates from mobile devices
    """
    authentication_classes = [TokenAuthentication]  # Add this
    permission_classes = [IsAuthenticated, IsDriverUser]  # Add IsAuthenticated
    
    def post(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
            serializer = DriverLocationUpdateSerializer(data=request.data)
            
            if serializer.is_valid():
                lat = serializer.validated_data['latitude']
                lng = serializer.validated_data['longitude']
                accuracy = serializer.validated_data.get('accuracy')
                speed = serializer.validated_data.get('speed')
                bearing = serializer.validated_data.get('bearing')
                battery_level = serializer.validated_data.get('battery_level')
                timestamp = serializer.validated_data.get('timestamp') or timezone.now()
                address = serializer.validated_data.get('address', '')
                parcel_id = serializer.validated_data.get('parcel_id')
                
                # Update driver location
                driver.current_location_lat = lat
                driver.current_location_lng = lng
                driver.last_location_update = timestamp
                
                # Update additional fields if provided
                if accuracy is not None:
                    driver.accuracy = accuracy
                if battery_level is not None:
                    driver.battery_level = battery_level
                
                driver.save()
                
                # Update all assigned parcels' current location
                assigned_parcels = Parcel.objects.filter(
                    assigned_driver=driver,
                    approval_status='approved',
                    status__in=['Assigned', 'Picked_Up', 'In_Transit', 'Out_for_Delivery']
                )
                
                for parcel in assigned_parcels:
                    parcel.current_location_lat = lat
                    parcel.current_location_lng = lng
                    parcel.save()
                    
                    # Get address from coordinates if not provided
                    if not address:
                        address = self.get_address_from_coords(lat, lng)
                    
                    # Record location history
                    LocationHistory.objects.create(
                        parcel=parcel,
                        latitude=lat,
                        longitude=lng,
                        address=address,
                        status=parcel.status
                    )
                    
                    # Create speed/distance tracking event if speed is significant
                    if speed and speed > 5:  # Speed in km/h
                        TrackingEvent.objects.create(
                            parcel=parcel,
                            status='In_Transit',
                            description=f'Driver moving at {speed:.1f} km/h towards destination',
                            location=address,
                            created_by=driver.user
                        )
                
                # If specific parcel ID provided, update that parcel
                if parcel_id:
                    try:
                        specific_parcel = Parcel.objects.get(id=parcel_id, assigned_driver=driver)
                        specific_parcel.current_location_lat = lat
                        specific_parcel.current_location_lng = lng
                        specific_parcel.save()
                    except Parcel.DoesNotExist:
                        pass
                
                return Response({
                    'success': True,
                    'message': 'Location updated successfully',
                    'timestamp': timestamp,
                    'accuracy': accuracy
                })
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def get_address_from_coords(self, lat, lng):
        """Convert coordinates to address using geopy"""
        try:
            geolocator = Nominatim(user_agent="im_courier")
            location = geolocator.reverse(f"{lat}, {lng}", language='en')
            return location.address if location else "Location not available"
        except Exception:
            return f"Lat: {lat}, Lng: {lng}"

class DriverStatusUpdateView(APIView):
    """
    Update driver online/offline status and tracking preferences
    """
    permission_classes = [IsDriverUser]
    
    def post(self, request):
        try:
            driver = Driver.objects.get(user=request.user)
            serializer = DriverStatusSerializer(data=request.data)
            
            if serializer.is_valid():
                is_online = serializer.validated_data['is_online']
                tracking_interval = serializer.validated_data.get('tracking_interval')
                device_token = serializer.validated_data.get('device_token')
                
                driver.is_online = is_online
                
                if tracking_interval:
                    driver.tracking_interval = tracking_interval
                
                if device_token is not None:
                    driver.device_token = device_token
                
                driver.save()
                
                return Response({
                    'success': True,
                    'message': f'Driver is now {"online" if is_online else "offline"}',
                    'tracking_interval': driver.tracking_interval,
                    'is_online': driver.is_online
                })
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class DriverRouteTrackingView(APIView):
    """
    Track driver's route for a specific parcel
    """
    permission_classes = [IsDriverUser]
    
    def post(self, request, parcel_id):
        try:
            driver = Driver.objects.get(user=request.user)
            parcel = Parcel.objects.get(id=parcel_id, assigned_driver=driver)
            
            serializer = DriverLocationUpdateSerializer(data=request.data)
            
            if serializer.is_valid():
                lat = serializer.validated_data['latitude']
                lng = serializer.validated_data['longitude']
                accuracy = serializer.validated_data.get('accuracy')
                speed = serializer.validated_data.get('speed')
                timestamp = serializer.validated_data.get('timestamp') or timezone.now()
                
                # Update driver and parcel location
                driver.current_location_lat = lat
                driver.current_location_lng = lng
                driver.last_location_update = timestamp
                
                if accuracy is not None:
                    driver.accuracy = accuracy
                
                driver.save()
                
                parcel.current_location_lat = lat
                parcel.current_location_lng = lng
                parcel.save()
                
                # Get address
                address = serializer.validated_data.get('address', '')
                if not address:
                    geolocator = Nominatim(user_agent="im_courier")
                    try:
                        location = geolocator.reverse(f"{lat}, {lng}", language='en')
                        address = location.address if location else f"Lat: {lat}, Lng: {lng}"
                    except Exception:
                        address = f"Lat: {lat}, Lng: {lng}"
                
                # Calculate distance to destination
                if parcel.delivery_location_coords:
                    # You would need to store delivery location coordinates
                    current_coords = (float(lat), float(lng))
                    dest_coords = parcel.delivery_location_coords
                    distance_km = geodesic(current_coords, dest_coords).kilometers
                    
                    # Create tracking event with distance info
                    TrackingEvent.objects.create(
                        parcel=parcel,
                        status='In_Transit',
                        description=f'Driver {distance_km:.1f} km from destination. Speed: {speed or 0} km/h',
                        location=address,
                        created_by=driver.user
                    )
                else:
                    # Regular location update
                    LocationHistory.objects.create(
                        parcel=parcel,
                        latitude=lat,
                        longitude=lng,
                        address=address,
                        status=parcel.status
                    )
                
                return Response({
                    'success': True,
                    'message': 'Route location updated',
                    'parcel_id': parcel.id,
                    'tracking_number': parcel.tracking_number,
                    'distance_remaining': 'Calculated if destination coords available'
                })
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Parcel.DoesNotExist:
            return Response(
                {'error': 'Parcel not found or not assigned to you'},
                status=status.HTTP_404_NOT_FOUND
            )

class DriverLocationHistoryView(generics.ListAPIView):
    """
    Get location history for a driver or specific parcel
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LocationHistorySerializer
    
    def get_queryset(self):
        driver_id = self.kwargs.get('driver_id')
        parcel_id = self.request.query_params.get('parcel_id')
        
        if driver_id:
            # Get driver's location history
            return LocationHistory.objects.filter(
                parcel__assigned_driver_id=driver_id
            ).order_by('-timestamp')[:100]
        elif parcel_id and self.request.user.has_perm('api.can_view_all_parcels'):
            # Admin view of parcel location history
            return LocationHistory.objects.filter(
                parcel_id=parcel_id
            ).order_by('-timestamp')
        else:
            return LocationHistory.objects.none()




# api/views.py - Add this view for web-specific tracking
class WebGPSTrackingView(APIView):
    """
    Web-specific GPS tracking endpoint
    """
    permission_classes = [IsDriverUser]
    
    def get(self, request):
        """Get current tracking status and settings"""
        try:
            driver = Driver.objects.get(user=request.user)
            assigned_parcels = Parcel.objects.filter(
                assigned_driver=driver,
                approval_status='approved',
                status__in=['Assigned', 'Picked_Up', 'In_Transit', 'Out_for_Delivery']
            ).select_related('sender', 'recipient')
            
            # Get recent location history
            recent_locations = LocationHistory.objects.filter(
                parcel__assigned_driver=driver
            ).order_by('-timestamp')[:10]
            
            serializer = ParcelSerializer(assigned_parcels, many=True)
            
            return Response({
                'driver': {
                    'is_online': driver.is_online,
                    'is_tracking': driver.last_location_update and 
                                  (timezone.now() - driver.last_location_update).seconds < 60,
                    'current_location': {
                        'lat': driver.current_location_lat,
                        'lng': driver.current_location_lng,
                    } if driver.current_location_lat else None,
                    'last_update': driver.last_location_update,
                    'accuracy': driver.accuracy,
                },
                'assigned_parcels': serializer.data,
                'recent_locations': LocationHistorySerializer(recent_locations, many=True).data,
            })
            
        except Driver.DoesNotExist:
            return Response(
                {'error': 'Driver not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        """Start/stop web tracking"""
        driver = Driver.objects.get(user=request.user)
        action = request.data.get('action')
        
        if action == 'start':
            driver.is_online = True
            driver.save()
            
            # Create tracking session
            TrackingSession.objects.create(
                driver=driver,
                start_time=timezone.now(),
                device_type='web',
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            
            return Response({
                'success': True,
                'message': 'Web tracking started',
                'tracking_interval': driver.tracking_interval,
            })
            
        elif action == 'stop':
            driver.is_online = False
            driver.save()
            
            # Update tracking session
            session = TrackingSession.objects.filter(
                driver=driver,
                end_time__isnull=True
            ).last()
            
            if session:
                session.end_time = timezone.now()
                session.save()
            
            return Response({
                'success': True,
                'message': 'Web tracking stopped',
            })
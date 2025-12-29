# api/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
import re

from .models import (
    Service, Parcel, Driver, LocationHistory,
    TrackingEvent, ApprovalLog
)


# === AUTH SERIALIZERS ===
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('username', None)  # Remove default

    def validate(self, attrs):
        username_input = attrs.get('username', '').strip()
        email_input = attrs.get('email', '').strip()
        password = attrs.get('password')

        if not password:
            raise serializers.ValidationError({'detail': 'Password is required.'})

        if not username_input and not email_input:
            raise serializers.ValidationError({
                'detail': 'You must provide either username or email.'
            })

        # Find user
        user = None
        if email_input:
            try:
                user = User.objects.get(email__iexact=email_input)
            except User.DoesNotExist:
                pass

        if not user and username_input:
            try:
                user = User.objects.get(username__iexact=username_input)
            except User.DoesNotExist:
                pass

        if not user:
            raise serializers.ValidationError({
                'detail': 'No account found with the provided credentials.'
            })

        if not user.is_active:
            raise serializers.ValidationError({'detail': 'Account is deactivated.'})

        # Authenticate
        authenticated_user = authenticate(
            request=self.context.get('request'),
            username=user.username,
            password=password
        )

        if not authenticated_user:
            raise serializers.ValidationError({'detail': 'Invalid password.'})

        self.user = authenticated_user
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

        # Add role and driver info
        try:
            driver = Driver.objects.get(user=self.user)
            data['user']['is_driver'] = True
            data['user']['driver_id'] = driver.id
            data['user']['role'] = 'driver'
        except Driver.DoesNotExist:
            data['user']['is_driver'] = False
            data['user']['role'] = 'admin' if self.user.is_staff else 'user'

        return data


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password2']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']


class UserProfileSerializer(serializers.ModelSerializer):
    is_driver = serializers.SerializerMethodField()
    is_approver = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'is_staff', 'is_driver', 'is_approver', 'date_joined']
        read_only_fields = ['id', 'is_staff', 'date_joined']

    def get_is_driver(self, obj):
        return Driver.objects.filter(user=obj).exists()

    def get_is_approver(self, obj):
        return obj.is_staff or obj.has_perm('api.can_approve_parcel')


# === OTHER SERIALIZERS ===
class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'


class DriverSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = Driver
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class ParcelSerializer(serializers.ModelSerializer):
    service_details = ServiceSerializer(source='service', read_only=True)
    driver_details = DriverSerializer(source='assigned_driver', read_only=True)
    approved_by_details = UserSerializer(source='approved_by', read_only=True)
    can_approve = serializers.SerializerMethodField()
    current_location = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        fields = '__all__'
        read_only_fields = [
            'tracking_number', 'status', 'approval_status', 'assigned_driver',
            'approved_by', 'approved_at', 'created_at', 'updated_at',
            'current_location_lat', 'current_location_lng', 'pickup_time',
            'delivery_time', 'current_location'
        ]

    def get_can_approve(self, obj):
        request = self.context.get('request')
        return request and request.user and (request.user.is_staff or request.user.has_perm('api.can_approve_parcel'))

    def get_current_location(self, obj):
        if obj.current_location_lat and obj.current_location_lng:
            return {
                'latitude': float(obj.current_location_lat),
                'longitude': float(obj.current_location_lng)
            }
        return None


class ParcelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parcel
        fields = '__all__'
        read_only_fields = [
            'tracking_number', 'status', 'approval_status', 'assigned_driver',
            'current_location_lat', 'current_location_lng', 'created_at',
            'updated_at', 'approved_by', 'approved_at', 'pickup_time',
            'delivery_time'
        ]

    def validate_sender_phone(self, value):
        if not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value

    def validate_receiver_phone(self, value):
        if not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value

    def validate_weight(self, value):
        if value <= 0:
            raise serializers.ValidationError("Weight must be greater than 0")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        parcel = Parcel.objects.create(**validated_data)

        TrackingEvent.objects.create(
            parcel=parcel,
            status='Awaiting_Approval',
            description='Parcel order submitted and awaiting approval',
            created_by=request.user if request and request.user.is_authenticated else None
        )

        # Email code (same as before)
        subject = f"I&M Courier - Parcel Request Submitted: {parcel.tracking_number}"
        message = f"""..."""  # keep your email template
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[parcel.sender_email],
            fail_silently=True,
        )

        return parcel


class BookDeliverySerializer(ParcelCreateSerializer):
    class Meta(ParcelCreateSerializer.Meta):
        fields = [
            'sender_name', 'sender_email', 'sender_phone',
            'receiver_name', 'receiver_email', 'receiver_phone',
            'pickup_location', 'delivery_location', 'weight',
            'dimensions', 'declared_value', 'service',
            'special_instructions'
        ]


class ParcelApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject', 'request_changes'])
    notes = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    assigned_driver_id = serializers.IntegerField(required=False)
    estimated_delivery = serializers.DateTimeField(required=False)


class LocationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationHistory
        fields = '__all__'


class TrackingEventSerializer(serializers.ModelSerializer):
    created_by_details = UserSerializer(source='created_by', read_only=True)
    class Meta:
        model = TrackingEvent
        fields = '__all__'


class ApprovalLogSerializer(serializers.ModelSerializer):
    performed_by_details = UserSerializer(source='performed_by', read_only=True)
    class Meta:
        model = ApprovalLog
        fields = '__all__'


class DriverLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    address = serializers.CharField(required=False, allow_blank=True)
    parcel_id = serializers.IntegerField(required=False)


class DriverLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    accuracy = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    speed = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    bearing = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    altitude = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    battery_level = serializers.IntegerField(required=False, min_value=0, max_value=100)
    timestamp = serializers.DateTimeField(required=False)
    address = serializers.CharField(required=False, allow_blank=True)
    parcel_id = serializers.IntegerField(required=False)


class DriverStatusSerializer(serializers.Serializer):
    is_online = serializers.BooleanField(required=True)
    tracking_interval = serializers.IntegerField(required=False, min_value=5, max_value=300)
    device_token = serializers.CharField(required=False, allow_blank=True)


# Optional other serializers
class PricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['id', 'name', 'description', 'price_per_kg', 'estimated_delivery_days']



class AreaSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    code = serializers.CharField(max_length=10)
    delivery_time = serializers.CharField(max_length=50)


class StatisticsSerializer(serializers.Serializer):
    total_parcels = serializers.IntegerField()
    delivered_parcels = serializers.IntegerField()
    pending_parcels = serializers.IntegerField()
    cancelled_parcels = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
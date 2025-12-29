# api/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
import uuid
from datetime import timedelta
from django.utils import timezone

def generate_tracking_number():
    return str(uuid.uuid4())[:8].upper()

class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estimated_delivery_days = models.IntegerField(default=3)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

# api/models.py - Add these to your Driver model
class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    phone_number = models.CharField(max_length=20)
    is_available = models.BooleanField(default=True)
    current_location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    vehicle_registration = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # New fields for GPS tracking
    is_online = models.BooleanField(default=False)  # Whether driver is actively tracking
    tracking_interval = models.IntegerField(default=30)  # Seconds between updates
    device_token = models.CharField(max_length=255, blank=True)  # For push notifications
    battery_level = models.IntegerField(null=True, blank=True)  # Device battery percentage
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # GPS accuracy in meters
    
    class Meta:
        verbose_name = "Driver"
        verbose_name_plural = "Drivers"
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.phone_number}"

class Parcel(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Awaiting_Approval', 'Awaiting Approval'),
        ('Approved', 'Approved'),
        ('Assigned', 'Assigned'),
        ('Picked_Up', 'Picked Up'),
        ('In_Transit', 'In Transit'),
        ('Out_for_Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Rejected', 'Rejected'),
    ]
    
    APPROVAL_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('under_review', 'Under Review'),
    ]
    
    tracking_number = models.CharField(max_length=50, unique=True, default=generate_tracking_number, editable=False)
    sender_name = models.CharField(max_length=100)
    sender_email = models.EmailField()
    sender_phone = models.CharField(max_length=20)
    receiver_name = models.CharField(max_length=100)
    receiver_email = models.EmailField()
    receiver_phone = models.CharField(max_length=20)
    pickup_location = models.CharField(max_length=200)
    delivery_location = models.CharField(max_length=200)
    weight = models.FloatField()
    dimensions = models.CharField(max_length=100, blank=True)
    declared_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='pending')
    assigned_driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True)
    current_location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_parcels')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    pickup_time = models.DateTimeField(null=True, blank=True)
    delivery_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Parcel"
        verbose_name_plural = "Parcels"
        permissions = [
            ('can_approve_parcel', 'Can approve parcel requests'),
            ('can_view_all_parcels', 'Can view all parcels'),
            ('can_assign_driver', 'Can assign driver to parcel'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return self.tracking_number
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_approval_status = None
        old_status = None
        
        if not is_new:
            old_obj = Parcel.objects.get(pk=self.pk)
            old_approval_status = old_obj.approval_status
            old_status = old_obj.status
        
        # Set estimated delivery if not set and service is selected
        if not self.estimated_delivery and self.service:
            self.estimated_delivery = timezone.now() + timedelta(days=self.service.estimated_delivery_days)
        
        super().save(*args, **kwargs)
        
        # Send emails on status changes
        if old_approval_status != self.approval_status or old_status != self.status:
            self.send_status_notification(old_approval_status, old_status)
    
    def send_status_notification(self, old_approval_status=None, old_status=None):
        # Send approval email
        if self.approval_status == 'approved' and old_approval_status != 'approved':
            subject = f"I&M Courier - Parcel Approved: {self.tracking_number}"
            message = f"""
Dear {self.sender_name},

Your parcel has been APPROVED!

Tracking Details:
- Tracking Number: {self.tracking_number}
- Status: {self.get_status_display()}
- Sender: {self.sender_name}
- Receiver: {self.receiver_name}
- Pickup: {self.pickup_location}
- Delivery: {self.delivery_location}
- Weight: {self.weight} kg

You can now track your parcel using this link:
{settings.FRONTEND_URL}/track/{self.tracking_number}

Thank you for choosing I&M Courier!

Best regards,
I&M Courier General Supplier
"""
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.sender_email, self.receiver_email],
                fail_silently=True,
            )
        
        # Send rejection email
        elif self.approval_status == 'rejected' and old_approval_status != 'rejected':
            subject = f"I&M Courier - Parcel Request Update: {self.tracking_number}"
            message = f"""
Dear {self.sender_name},

We regret to inform you that your parcel request has been REJECTED.

Details:
- Tracking Number: {self.tracking_number}
- Reason for Rejection: {self.rejection_reason}

You can contact our customer service for more information or to resubmit your request.

Thank you for considering I&M Courier.

Best regards,
I&M Courier General Supplier
"""
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.sender_email],
                fail_silently=True,
            )
        
        # Send delivery status updates
        elif self.status == 'Delivered' and old_status != 'Delivered':
            subject = f"I&M Courier - Parcel Delivered: {self.tracking_number}"
            message = f"""
Dear {self.receiver_name},

Your parcel has been DELIVERED!

Tracking Details:
- Tracking Number: {self.tracking_number}
- Delivered To: {self.receiver_name}
- Delivery Location: {self.delivery_location}
- Delivery Time: {self.delivery_time}

Thank you for choosing I&M Courier!

Best regards,
I&M Courier General Supplier
"""
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.sender_email, self.receiver_email],
                fail_silently=True,
            )



class TrackingSession(models.Model):
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='tracking_sessions')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    device_type = models.CharField(max_length=20, choices=[
        ('web', 'Web Browser'),
        ('android', 'Android App'),
        ('ios', 'iOS App'),
    ])
    user_agent = models.TextField(blank=True)
    locations_count = models.IntegerField(default=0)
    distance_traveled = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # km
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.driver} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class LocationHistory(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='location_history')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField(auto_now_add=True)
    address = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=50)
    tracking_session = models.ForeignKey(TrackingSession, on_delete=models.SET_NULL, 
                                        null=True, blank=True, related_name='locations')
    
    class Meta:
        verbose_name = "Location History"
        verbose_name_plural = "Location Histories"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.parcel.tracking_number} - {self.timestamp}"

class TrackingEvent(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=50)
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Tracking Event"
        verbose_name_plural = "Tracking Events"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.parcel.tracking_number} - {self.status}"

class ApprovalLog(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='approval_logs')
    action = models.CharField(max_length=50)  # APPROVED, REJECTED, REQUESTED_CHANGES
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Approval Log"
        verbose_name_plural = "Approval Logs"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.parcel.tracking_number} - {self.action}"









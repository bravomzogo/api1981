# api/admin.py
from django.contrib import admin
from .models import Service, Parcel, Driver, LocationHistory, TrackingEvent, ApprovalLog

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_per_kg', 'estimated_delivery_days', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']

@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ['tracking_number', 'sender_name', 'receiver_name', 'status', 
                   'approval_status', 'created_at', 'estimated_delivery']
    list_filter = ['status', 'approval_status', 'created_at']
    search_fields = ['tracking_number', 'sender_name', 'sender_email', 
                    'receiver_name', 'receiver_email']
    readonly_fields = ['tracking_number', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('tracking_number', 'sender_name', 'sender_email', 'sender_phone',
                      'receiver_name', 'receiver_email', 'receiver_phone')
        }),
        ('Parcel Details', {
            'fields': ('pickup_location', 'delivery_location', 'weight', 'dimensions',
                      'declared_value', 'service', 'special_instructions')
        }),
        ('Status and Tracking', {
            'fields': ('status', 'approval_status', 'assigned_driver', 
                      'current_location_lat', 'current_location_lng',
                      'estimated_delivery', 'pickup_time', 'delivery_time',
                      'approved_by', 'approved_at', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'is_available', 'vehicle_registration']
    list_filter = ['is_available']
    search_fields = ['user__username', 'user__email', 'phone_number']

@admin.register(LocationHistory)
class LocationHistoryAdmin(admin.ModelAdmin):
    list_display = ['parcel', 'latitude', 'longitude', 'timestamp', 'status']
    list_filter = ['timestamp', 'status']
    search_fields = ['parcel__tracking_number']

@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ['parcel', 'status', 'timestamp', 'created_by']
    list_filter = ['status', 'timestamp']
    search_fields = ['parcel__tracking_number', 'description']

@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ['parcel', 'action', 'performed_by', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['parcel__tracking_number', 'notes']

# Set admin site headers
admin.site.site_header = "I&M Courier Admin"
admin.site.site_title = "I&M Courier Admin Portal"
admin.site.index_title = "Welcome to I&M Courier Admin Portal"
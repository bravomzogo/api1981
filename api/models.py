from django.db import models
import uuid

def generate_tracking_number():
    return str(uuid.uuid4())[:8].upper()

class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name

class Parcel(models.Model):
    tracking_number = models.CharField(max_length=50, unique=True, default=generate_tracking_number)
    sender_name = models.CharField(max_length=100)
    receiver_name = models.CharField(max_length=100)
    pickup_location = models.CharField(max_length=200)
    delivery_location = models.CharField(max_length=200)
    weight = models.FloatField()
    status = models.CharField(max_length=50, default='Inafikia')  # Swahili for 'Pending'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.tracking_number
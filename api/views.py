from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Service, Parcel
from .serializers import ServiceSerializer, ParcelSerializer

class ServiceListView(generics.ListAPIView):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer

class BookDeliveryView(generics.CreateAPIView):
    queryset = Parcel.objects.all()
    serializer_class = ParcelSerializer

class TrackParcelView(APIView):
    def get(self, request, tracking_number):
        try:
            parcel = Parcel.objects.get(tracking_number=tracking_number)
            serializer = ParcelSerializer(parcel)
            return Response(serializer.data)
        except Parcel.DoesNotExist:
            return Response({"error": "Mzigo haujapatikana"}, status=404)

class PricingView(APIView):
    def get(self, request):
        pricing = [
            {"huduma": "Local Delivery", "bei": "Kwa uzito chini ya 1kg: TZS 5,000"},
            {"huduma": "International Shipping", "bei": "Kulingana na umbali"},
            {"huduma": "Same-Day Delivery", "bei": "TZS 10,000 - 20,000"},
        ]
        return Response(pricing)

class AreasView(APIView):
    def get(self, request):
        areas = ["Dar es Salaam", "Arusha", "Mwanza", "International"]
        return Response(areas)
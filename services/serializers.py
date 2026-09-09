from rest_framework import serializers
from .models import EstateService, Service, ServiceRequest

class ServiceSerializer(serializers.ModelSerializer):
    image = serializers.ReadOnlyField()

    class Meta:
        model = Service
        fields = ['id', 'name', 'description', 'image']

class AvailableEstateServiceSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)
    provider_name = serializers.CharField(source='provider.brand_name', read_only=True)

    class Meta:
        model = EstateService
        fields = ['id', 'service', 'request_fee', 'provider_name']

class ServiceRequestSerializer(serializers.ModelSerializer):
    estate_service_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ServiceRequest
        fields = ['id', 'estate_service_id', 'notes', 'fee_paid', 'status']
        read_only_fields = ['id', 'fee_paid', 'status']


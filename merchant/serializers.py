from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from decimal import Decimal
from products.models import Product
from .models import Merchant, MerchantProduct
from django.contrib.auth import get_user_model
from django.db.models import Avg
from website.models import SiteConfiguration
from products.serializers import ProductImagesSerializer




class MerchantSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    class Meta:
        model = Merchant
        fields = ['id', 'store_name', 'category', 'brand_logo']
        read_only_fields = ['id', 'store_name', 'category']



class NoPriceProductSerializer(serializers.ModelSerializer):

    categories_display = serializers.SerializerMethodField(read_only=True)
    images=ProductImagesSerializer(read_only=True,many=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'package' , 'description', 'categories_display', 'images']

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_categories_display(self, obj):
        return [cat.name for cat in obj.categories.all()]
    
    
    


class MerchantProductSerializer(serializers.ModelSerializer):
    product = NoPriceProductSerializer (read_only=True)
    merchant = serializers.StringRelatedField()
    # average_rating = serializers.SerializerMethodField()

    class Meta:
        model = MerchantProduct
        fields = ['id', 'product', 'price', 'merchant', 'average_rating']
        read_only_fields = ['id', 'product', 'price', 'merchant', 'average_rating']

    # @extend_schema_field(serializers.FloatField)
    # def get_average_rating(self, obj):
    #     return obj.reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
        


class NoPriceProductListSerializer(serializers.ModelSerializer):
    # image = serializers.SerializerMethodField(read_only=True)
    categories_display = serializers.SerializerMethodField() # Added to match your method

    class Meta:
        model = Product
        fields = ['id', 'name', 'image', 'categories_display']

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_categories_display(self, obj):
        # Uses prefetched data (no DB hit)
        return [cat.name for cat in obj.categories.all()]
    


class MerchantProductListSerializer(serializers.ModelSerializer):
    product = NoPriceProductListSerializer (read_only=True)
    merchant = serializers.StringRelatedField()
    class Meta:
        model = MerchantProduct
        fields = ['id', 'product', 'price', 'merchant', 'average_rating']
        read_only_fields = ['id', 'product', 'price', 'merchant', 'average_rating',]







class NoIdProductSearchSuggestionSerializer(serializers.ModelSerializer):
    # We pull the image string directly from our optimized queryset annotation
    image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = ['name', 'image_url']



class MerchantProductSuggestionSerializer(serializers.ModelSerializer):
    product = NoIdProductSearchSuggestionSerializer (read_only=True)
 
    class Meta:
        model = MerchantProduct
        fields = ['id', 'product']
        read_only_fields = ['id', 'product']

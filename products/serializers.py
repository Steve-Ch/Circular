from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from decimal import Decimal
from .models import (
    Product, Cart,CartItem,Order,
    OrderItem,ProductImage,Review,
    Category, RefundRequest
    )
from django.contrib.auth import get_user_model
from django.db.models import Avg


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Review
        fields = ['id', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['image',]

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['name',]






class ProductSerializer(serializers.ModelSerializer):

    # categories = serializers.ListField(
    #     child=serializers.CharField(min_length=5),
    #     min_length=1, required=True, write_only=True
    # )

    average_rating = serializers.SerializerMethodField()
    categories_display = serializers.SerializerMethodField(read_only=True)
    images=ProductImagesSerializer(read_only=True,many=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'categories_display', 'price', 'average_rating', 'images']

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_categories_display(self, obj):
        return [cat.name for cat in obj.categories.all()]
    
    @extend_schema_field(serializers.FloatField)
    def get_average_rating(self, obj):
        return obj.reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    
    


class ProductListSerializer(serializers.ModelSerializer):
    average_rating = serializers.FloatField(source='avg_rating', read_only=True)
    # image = serializers.SerializerMethodField(read_only=True)
    categories_display = serializers.SerializerMethodField() # Added to match your method

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'image', 'average_rating', 'categories_display']

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_categories_display(self, obj):
        # Uses prefetched data (no DB hit)
        return [cat.name for cat in obj.categories.all()]
    

class ProductSearchSuggestionSerializer(serializers.ModelSerializer):
    # We pull the image string directly from our optimized queryset annotation
    image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'image_url']




class CartItemSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField()
    # Adding a subtotal field is often helpful for cart UI
    total_price = serializers.SerializerMethodField()
    

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'image', 'price', 'quantity', 'total_price']
        read_only_fields = ['id', 'product', 'price', 'total_price']
        extra_kwargs = {
            "quantity": {"required": True},
            
        }
        

    @extend_schema_field(Decimal)
    def get_total_price(self, obj):
        return obj.quantity * obj.product.price


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(read_only=True, many=True)
    class Meta:
        model = Cart
        fields = ['items', 'price_total',]



class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField()
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'price_at_purchase']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(read_only=True, many=True)
    class Meta:
        model = Order
        fields = ['id', 'full_name', 'items', 'price_total', 'email', 'status', 'reference', 'address' ]


class CheckoutResponseSerializer(serializers.Serializer):
    reference = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)
    status = serializers.CharField()
    checkout_url = serializers.URLField()


class CancelOrderSerializer(serializers.ModelSerializer):
    # Enforce validation using your model's text choices
    cancellation_reason = serializers.ChoiceField(choices=RefundRequest.CANCELLATION_REASONS.choices)

    class Meta:
        model = RefundRequest
        fields = ['cancellation_reason', 'cancellation_note']

    def create(self, validated_data):
        print(validated_data)
        # Fetch the order injected from the view's perform_create
        order = validated_data['order']
        
        # 1. Update the parent order status to CANCELLED

        order.status = order.Status.CANCELLED
        order.save()
        

        
        # 2. Extract Paystack reference if a transaction exists on the order
        paystack_ref = order.reference() if order.transaction else None

        return RefundRequest.objects.create(
            paystack_reference=paystack_ref,
            **validated_data
        )

from rest_framework import serializers
from .models import (
    Product, Cart,
    CartItem,Order,
    OrderItem,
    )

class ProductSerializer(serializers.ModelSerializer):

    # categories = serializers.ListField(
    #     child=serializers.CharField(min_length=5),
    #     min_length=1, required=True, write_only=True
    # )
    categories_display = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = Product
        fields = ['id', 'name', 'categories_display', 'price', 'quantity',]

    # @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_categories_display(self, obj):
        return [cat.name for cat in obj.categories.all()]




class CartItemSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField()
    # Adding a subtotal field is often helpful for cart UI
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'price', 'quantity', 'total_price']
        # 'quantity' is excluded from read_only so it can be updated
        read_only_fields = ['id', 'product', 'price', 'total_price']

    def get_total_price(self, obj):
        return obj.quantity * obj.price


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

from django.shortcuts import render
from rest_framework import generics, status, permissions, parsers, exceptions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .paginations import StandardResultsSetPagination
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import (
    Product, Cart,
    CartItem,Order,
    OrderItem,
    )
from .serializers import (
    ProductSerializer, 
    CartSerializer, 
    OrderSerializer,
    CartItemSerializer
    )

# Create your views here.



class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categories__name',]
    search_fields = ['name']
    pagination_class = StandardResultsSetPagination



class ProductRetrieveAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(quantity__gte=1)
    serializer_class = ProductSerializer
    lookup_field = 'pk'



class OrderListAPIView(generics.ListAPIView):
    serializer_class = OrderSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Order.objects.filter(user=user)



class OrderRetrieveAPIView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        return Order.objects.filter(user=user)
    

class CartRetrieveAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # self.check_object_permissions(self.request, obj)
        cart = Cart.objects.get_or_create(user=self.request.user)
        return cart

class CartItemCreateAPIView(generics.CreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    # queryset = CartItem.objects.all()

    def perform_create(self, serializer):
        Product_id = self.kwargs.get('product_id')
        
        product = get_object_or_404(Product, pk=Product_id)
        cart = Cart.objects.get_or_create(user=self.request.user)
        quantity = serializer.validated_data.get['quantity']
        if quantity > product.quantity:
            raise ValidationError({'quantity':'you cant order more than the available quantity'})
        serializer.save(product=product, cart=cart)


class CartItemUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        return CartItem.objects.filter(user=user)
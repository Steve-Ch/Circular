from django.shortcuts import render
from rest_framework import generics, status, permissions, parsers, exceptions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.response import Response
from rest_framework.views import APIView
from .paginations import StandardResultsSetPagination
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from drf_spectacular.utils import extend_schema
from .utils import initiate_payment, paystack_verify, finalize_order
from django.conf import settings
import threading
from .models import (
    Product, Cart,
    CartItem,Order,
    OrderItem, Transaction
    )
from .serializers import (
    ProductSerializer, 
    CartSerializer, 
    OrderSerializer,
    CartItemSerializer,
    CheckoutResponseSerializer,
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
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()

        if not self.request.user.is_authenticated:
            return Order.objects.none()

        return Order.objects.filter(user=self.request.user)


class OrderRetrieveAPIView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        return Order.objects.filter(user=user)
    

class CartRetrieveAPIView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # self.check_object_permissions(self.request, obj)
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        return cart

class CartItemCreateAPIView(generics.CreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    # queryset = CartItem.objects.all()

    def perform_create(self, serializer):
        Product_id = self.kwargs.get('product_id')
        
        product = get_object_or_404(Product, pk=Product_id)
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        quantity = serializer.validated_data.get('quantity')
        if quantity > product.quantity:
            raise ValidationError({"quantity":"you can't order more than the available quantity"})
        serializer.save(product=product, cart=cart)


class CartItemUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        return CartItem.objects.filter(cart=user.cart)



class CheckoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CheckoutResponseSerializer 

    @extend_schema(request=None)
    def post(self, request, *args, **kwargs):
        
        # serializer = self.get_serializer(data=request.data)
        # serializer.is_valid(raise_exception=True)
        # data = serializer.validated_data
        # address_id = data.get('address_id')
        # address = user.addresses.filter(id = address_id)
        address = request.data.user.address
        if not address.exist():
            raise PermissionDenied("Address not Found, for this user") 

        user = request.user
        cart = Cart.objects.get(user=user)
        transaction_obj = Transaction.objects.create(
            user=user, 
            amount=cart.price_total, 
            status=Transaction.Status.PENDING
        )

        pay_res = initiate_payment(
            amount=cart.price_total, 
            email=user.email, 
            reference=transaction_obj.reference
        )

        if pay_res.get('status'):
            data = {
                "reference": transaction_obj.reference,
                "amount": transaction_obj.amount,
                "status": transaction_obj.status,
                "checkout_url": pay_res['data']['authorization_url']
            }
            return Response(self.get_serializer(data).data, status=status.HTTP_201_CREATED)
        
        return Response({
            "error": "Payment failed",
            "data": pay_res,
            }, status=status.HTTP_400_BAD_REQUEST)
    

#webhook
class paystack_webhook(APIView):
    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):

        key = self.kwargs.get('key')
        if key == settings.SIGNATURE_KEY:

            # main logic
            data = request.data.get("data")


            # create thread for quick responce
            # payment_verification = threading.Thread(
            #     target=payment_verify,
            #     args=[data['reference'], data['status']],
            # )

            # payment_verification.start()
            
            finalize_order(data['reference'], data['status'])

            return Response({}, status=200)

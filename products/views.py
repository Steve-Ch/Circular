from django.db.models import F
from django.shortcuts import render
from rest_framework import generics, status, permissions, parsers, exceptions, serializers
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
from .models import (
    Product, Cart,CartItem,Order,
    Review,Transaction, WishlistItem,
    ProductImage, Category,RefundRequest,
    )
from website.models import SiteConfiguration
from .serializers import (
    ProductSerializer, 
    CartSerializer, 
    OrderSerializer,
    CartItemSerializer,
    CheckoutResponseSerializer,
    ProductListSerializer,
    CategorySerializer,
    ReviewSerializer,
    CancelOrderSerializer,
    WishlistReadSerializer, 
    WishlistWriteSerializer,
    ProductSearchSuggestionSerializer
    )
from django.db import transaction

# Create your views here.

from django.db.models import OuterRef, Subquery



class ProductListAPIView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(display=True)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categories__name',]
    search_fields = ['name']
    pagination_class = StandardResultsSetPagination



class ProductSearchSuggestionAPIView(generics.ListAPIView):
    serializer_class = ProductSearchSuggestionSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    
    # Disable pagination for suggestions so it doesn't return full pagination metadata
    pagination_class = None 

    def get_queryset(self):
        first_image_subquery = ProductImage.objects.filter(
            product=OuterRef('pk')
        ).order_by('-created_at').values('image')[:1]

        # REMOVED [:10] FROM THE END HERE
        return Product.objects.filter(display=True).annotate(
            image_url=Subquery(first_image_subquery)
        ).only('id', 'name').order_by('name')

    def list(self, request, *args, **kwargs):
        """Override list to safely slice the results AFTER filters have been applied."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Safely slice the evaluated/filtered queryset to exactly 10 items
        serializer = self.get_serializer(queryset[:10], many=True)
        from rest_framework.response import Response
        return Response(serializer.data)



class CategoryListAPIView(generics.ListAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()



class ReviewListAPIView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        pk = self.kwargs['pk']
        return Review.objects.filter(product_id = pk)



class ReviewDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # This ensures the user only ever interacts with THEIR review for THIS product
        product_id = self.kwargs.get('pk')
        return Review.objects.filter(user=self.request.user, product_id=product_id).first()

    def post(self, request, *args, **kwargs):
        # Custom logic to handle "Create or Update" in one POST request
        instance = self.get_object()
        if instance:
            # Update existing
            serializer = self.get_serializer(instance, data=request.data, partial=True)
        else:
            # Create new
            serializer = self.get_serializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user, product_id=self.kwargs.get('pk'))
        
        return Response(serializer.data, status=status.HTTP_200_OK if instance else status.HTTP_201_CREATED)



class ProductRetrieveAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(display=True)
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


class CartItemCreateAPIView(generics.CreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        product_id = self.kwargs.get('product_id')
        product = get_object_or_404(Product, pk=product_id)
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        
        # Validate the incoming data structure first
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_quantity = serializer.validated_data.get('quantity')

        # Check if this product is already in the user's cart
        existing_item = CartItem.objects.filter(cart=cart, product=product).first()

        if existing_item:
            # Calculate total quantity if we add the new request
            new_quantity = existing_item.quantity + requested_quantity
            
            # Check against the product stock limit
            # if new_quantity > product.quantity:
            #     raise ValidationError({
            #         "quantity": f"You can't add more items. Max available is {product.quantity}. You already have {existing_item.quantity} in cart."
            #     })
            
            # Update existing instance and save
            existing_item.quantity = new_quantity
            existing_item.save()
            
            # Serialize the updated item to return it in the response
            return_serializer = self.get_serializer(existing_item)
            return Response(return_serializer.data, status=status.HTTP_200_OK)
        
        # If item doesn't exist in cart yet, perform standard check and creation
        # if requested_quantity > product.quantity:
        #     raise ValidationError({"quantity": f"You can't order more than the available quantity ({product.quantity})."})
            
        serializer.save(product=product, cart=cart)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



class CartItemUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        return CartItem.objects.filter(cart=user.cart)



class ClearCartAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        # Fetch the user's cart (or 404 if they somehow don't have one yet)
        cart = get_object_or_404(Cart, user=request.user)
        
        # Delete all items attached to this cart
        cart.items.all().delete()
        
        # Return a 204 No Content response indicating success
        return Response(
            {"detail": "Cart cleared successfully."}
        )


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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        cart = Cart.objects.get(user=user)
        cart_items = cart.items.select_related('product')
        minimum_order = SiteConfiguration.objects.first().minimum_tx
        subtotal = cart.subtotal
        if subtotal < minimum_order:
                return Response({
                    "error": f"can't place order less that {minimum_order}."
                }, status=status.HTTP_400_BAD_REQUEST)
        callback_url = data.get('callback_url')

        # PRE-CHECK: Don't even start payment if stock is already gone
        # for item in cart_items:
        #     if item.product.quantity < item.quantity:
        #         return Response({
        #             "error": f"Only {item.product.quantity} units of {item.product.name} left."
        #         }, status=status.HTTP_400_BAD_REQUEST)


        address = request.user.address
        if not address:
            raise PermissionDenied("Address not Found, for this user") 

        transaction_obj = Transaction.objects.create(
            user=user, 
            amount=cart.price_total, 
            status=Transaction.Status.PENDING
        )

        pay_res = initiate_payment(
            amount=cart.price_total, 
            email=user.email, 
            reference=transaction_obj.reference,
            callback_url = callback_url
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




class CancelOrderView(generics.CreateAPIView):
    serializer_class = CancelOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # 1. Look up the order using the UUID from the URL path variables
        order_id = self.kwargs.get("order_id")
        
        # 2. Ensure the order exists and belongs exclusively to the logged-in user
        order = get_object_or_404(Order, id=order_id, user=self.request.user)
        
        # 3. Guard: Prevent cancelling if it's already cancelled or delivered
        if order.status == Order.Status.CANCELLED:
            raise serializers.ValidationError({"detail": "This order has already been cancelled."})
        if order.status == Order.Status.DELIVERED:
            raise serializers.ValidationError({"detail": "Cannot cancel an order that has already been delivered."})
        if order.status == Order.Status.IN_PROGRESS:
            raise serializers.ValidationError({'detail':'cannot cancel, order is already on its way'})    
        # 4. Guard: OneToOneField safety check to avoid IntegrityError
        if RefundRequest.objects.filter(order=order).exists():
            raise serializers.ValidationError({"detail": "A cancellation request already exists for this order."})

        # 5. Pass the verified order object into the serializer's validated data
        serializer.save(order=order)





class WishlistListCreateView(generics.ListCreateAPIView):
    """Handles fetching user wishlist and adding new items."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistWriteSerializer

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return WishlistReadSerializer
        return WishlistWriteSerializer

    def perform_create(self, serializer):
        
        serializer.save(user=self.request.user)


class WishlistDestroyView(generics.DestroyAPIView):
    """Handles removing a single item directly from the wishlist."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistReadSerializer

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)


class WishlistMoveToCartView(generics.GenericAPIView):
    """Custom generic view to handle atomic transition from wishlist to cart."""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        wishlist_item = self.get_object()
        
        try:
            with transaction.atomic():
                # 1. Add or update the product in the user's cart
                cart, cart_created = Cart.objects.get_or_create(
                    user=request.user,
                )
                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=wishlist_item.product
                )
                
                if not created:
                    cart_item.quantity += 1
                    cart_item.save()

                # 2. Delete from wishlist safely inside the transaction block
                wishlist_item.delete()

            return Response(
                {"detail": "Product successfully moved to cart."}, 
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"detail": "Failed to complete the transfer operation."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

from django.urls import path
from .views import (
    ProductListAPIView,
    ProductRetrieveAPIView,
    OrderListAPIView,
    OrderRetrieveAPIView,
    CartRetrieveAPIView,
    CartItemCreateAPIView,
    CartItemUpdateDestroyAPIView,
    CheckoutView,
    paystack_webhook,
    ReviewListAPIView,
    ReviewDetailAPIView,
    CategoryListAPIView,
    CancelOrderView,
    ClearCartAPIView
)


urlpatterns = [
    path('products/', ProductListAPIView.as_view()),
    path('products/<uuid:pk>/', ProductRetrieveAPIView.as_view()),
    path('products/<uuid:pk>/reviews/', ReviewListAPIView.as_view()),
    path('products/<uuid:pk>/reviews/my-review/', ReviewDetailAPIView.as_view()),
    path('categories/', CategoryListAPIView.as_view()),
    path('my-orders/', OrderListAPIView.as_view()),
    path('my-orders/<uuid:pk>/', OrderRetrieveAPIView.as_view()),
    path('my-cart/', CartRetrieveAPIView.as_view()),
    path('my-cart/add/<uuid:product_id>', CartItemCreateAPIView.as_view()),
    path('my-cart/edit/<uuid:pk>/', CartItemUpdateDestroyAPIView.as_view()),
    path('my-cart/checkout/', CheckoutView.as_view()),
    path('my-cart/clear/', ClearCartAPIView.as_view(), name='clear-cart'),
    path('paystack-verify/<str:key>', paystack_webhook.as_view()),
    path('my-orders/<uuid:order_id>/cancel/', CancelOrderView.as_view(), name='cancel-order'),
]


from django.urls import path
from .views import (
    ProductListAPIView,
    ProductRetrieveAPIView,
    OrderListAPIView,
    OrderRetrieveAPIView,
    CartRetrieveAPIView,
    CartItemCreateAPIView,
    CartItemUpdateDestroyAPIView,
)


urlpatterns = [
    path('', ProductListAPIView.as_view()),
    path('products/<uuid:pk>/', ProductRetrieveAPIView.as_view()),
    path('my-orders/', OrderListAPIView.as_view()),
    path('my-orders/<uuid:pk>/', OrderRetrieveAPIView.as_view()),
    path('my-cart', CartRetrieveAPIView.as_view()),
    path('my-cart/add/<uuid:product_id>', CartItemCreateAPIView.as_view()),
    path('my-cart/edit/<uuid:pk>/', CartItemUpdateDestroyAPIView.as_view()),
]


from django.urls import path
from products.views import ReviewListAPIView,ReviewDetailAPIView
from .views import (
    MerchantProductSearchSuggestionAPIView,
    MerchantProductListAPIView, 
    MerchantProductRetrieveAPIView,
    PackagesAPIView
)


urlpatterns = [
    path('suggestions/', MerchantProductSearchSuggestionAPIView.as_view()),
    path('', MerchantProductListAPIView.as_view()),
    path('packages/', PackagesAPIView.as_view()),
    path('<uuid:id>/', MerchantProductRetrieveAPIView.as_view()),
    path('<uuid:id>/reviews/', ReviewListAPIView.as_view()),
    path('<uuid:id>/reviews/my-review/', ReviewDetailAPIView.as_view()),
]
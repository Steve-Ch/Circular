from django.shortcuts import render
from rest_framework import generics, status, permissions, parsers, exceptions, serializers
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from products.paginations import StandardResultsSetPagination
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from .models import (
    MerchantProduct
    )
from .serializers import (
    MerchantProductSerializer, 
    MerchantProductSuggestionSerializer, 
    MerchantProductListSerializer,
    MerchantSerializer,
    )
from products.models import Product, ProductImage
from django.db.models import OuterRef, Subquery
from .models import MerchantProduct, Merchant

from django.db.models import Case, When, Value, IntegerField, Subquery, OuterRef, F
from django.db.models.functions import RowNumber
from django.db.models.expressions import Window
from rest_framework import generics, filters
from rest_framework.response import Response





class MerchantListAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated] # 1. Block unauthenticated users
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['category__name', 'main_estates__name']
    search_fields = ['store_name']
    serializer_class = MerchantSerializer

    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'estate') and user.estate:
            return user.estate.main_merchants.all()
            
        # 3. Always return an empty queryset if they have no estate associated
        return Merchant.objects.none() 

        
        



class MerchantProductSearchSuggestionAPIView(generics.ListAPIView):
    filter_backends = [filters.SearchFilter]
    search_fields = ['product__name']
    pagination_class = None 
    serializer_class = MerchantProductSuggestionSerializer

    def get_queryset(self):
        user = self.request.user
        
        # Shared image subquery across all branches
        first_image_subquery = ProductImage.objects.filter(
            product=OuterRef('product_id')
        ).order_by('-created_at').values('image')[:1]

        # Base structure for authenticated users
        if user.is_authenticated and hasattr(user, 'estate') and user.estate:
            estate = user.estate
            
            # FIXED: Pluck IDs from both ManyToMany fields as lists
            main_merchant_ids = list(estate.main_merchants.values_list('id', flat=True))
            backup_merchant_ids = list(estate.backup_merchants.values_list('id', flat=True))
            
            # Merge both lists into a single collection for the base pool query
            all_merchant_ids = main_merchant_ids + backup_merchant_ids
            
            return MerchantProduct.objects.filter(
                merchant_id__in=all_merchant_ids,
                display=True,
                product__display=True
            ).annotate(
                image_url=Subquery(first_image_subquery)
            ).order_by('product__name')
        
        # Default workflow for guest users (Global Merchant)
        return MerchantProduct.objects.filter(
            merchant__store_name='Global Merchant',
            display=True,
            product__display=True
        ).annotate(
            image_url=Subquery(first_image_subquery)
        ).order_by('product__name')

    def list(self, request, *args, **kwargs):
        user = self.request.user
        
        # 1. Grab base pool and apply the SearchFilter
        base_queryset = self.get_queryset()
        filtered_queryset = self.filter_queryset(base_queryset)
        
        if user.is_authenticated and hasattr(user, 'estate') and user.estate:
            estate = user.estate
            
            # Target the specific main merchant IDs linked to this estate
            main_merchant_ids = estate.main_merchants.values_list('id', flat=True)
            main_merchant_results = filtered_queryset.filter(merchant_id__in=main_merchant_ids)
            
            # Rule: If main merchants have matching items, show only those!
            if main_merchant_results.exists():
                final_queryset = main_merchant_results
            else:
                # Fallback Rule: Show items from any matching backup merchants instead
                backup_merchant_ids = estate.backup_merchants.values_list('id', flat=True)
                final_queryset = filtered_queryset.filter(merchant_id__in=backup_merchant_ids)
        else:
            final_queryset = filtered_queryset

        # Slice to maximum 10 suggestion items
        serializer = self.get_serializer(final_queryset[:10], many=True)
        return Response(serializer.data)






class MerchantProductListAPIView(generics.ListAPIView):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['product__categories__name', 'merchant__category__name', 'merchant__store_name']
    search_fields = ['product__name']
    serializer_class = MerchantProductListSerializer

    def get_queryset(self):
        user = self.request.user
        
        # Check authentication FIRST, then check the estate relation
        if user.is_authenticated and hasattr(user, 'estate') and user.estate:
            merchants = user.estate.main_merchants.all()
            # Return private/personalized records for logged-in users
            return MerchantProduct.objects.filter(merchant__in=merchants, display=True).order_by('created_at')
            # return MerchantProduct.objects.filter(display=True)
        
        # Return only public records for anonymous guests
        return MerchantProduct.objects.filter(
                    merchant__store_name='Global Merchant',  # Change field name if match is by another field
                    display=True,
                    product__display=True
                )



class PackagesAPIView(generics.ListAPIView):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['product__categories__name', 'merchant__category__name']
    search_fields = ['product__name']
    serializer_class = MerchantProductListSerializer
    queryset = MerchantProduct.objects.filter(product__package=True)


    # # 1. DYNAMICALLY GENERATE SEARCH FIELDS
    # def get_search_fields(self, view, request):
    #     user = self.request.user
    #     if user.is_authenticated and hasattr(user, 'estate') and user.estate:
    #         # Fields matching the MerchantProduct model fields
    #         return ['product__name']
        
    #     # Fields matching the plain Product model fields
    #     return ['name']

    # # 2. DYNAMICALLY GENERATE FILTERSET FIELDS
    # def get_filterset_fields(self, v):
    #     user = self.request.user
    #     if user.is_authenticated and hasattr(user, 'estate') and user.estate:
    #         # Target path through the MerchantProduct foreign key
    #         return ['product__categories__name']
            
    #     # Target path directly on the Product model
    #     return ['categories__name']








class MerchantProductRetrieveAPIView(generics.RetrieveAPIView):
    serializer_class = MerchantProductSerializer
    lookup_field = 'id'
    queryset = MerchantProduct




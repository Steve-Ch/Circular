"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from website.views import admin_dashboard_stats

from website import views

urlpatterns = [
    path('admin/image-matcher/search/', views.search_unlinked_products, name='search_unlinked_products'),
    path('admin/image-matcher/link/', views.link_image_to_product, name='link_image_to_product'),
    path('admin/image-matcher/board/', views.get_next_matcher_board, name='matcher_board'),
    path('admin/image-matcher/skip/<int:unlinked_id>/', views.skip_image, name='skip_image'),
    path('admin/image-matcher/products/', views.match_by_product_list, name='match_by_product_list'),
    path('admin/image-matcher/upload/<uuid:product_id>/', views.direct_upload_to_product, name='direct_upload_to_product'),
    path('admin/dashboard-stats/', admin_dashboard_stats, name='admin_dashboard_stats'),
    path('admin/image-matcher/preview/<uuid:product_id>/<int:unlinked_id>/', views.preview_match, name='preview_match'),
    path('admin/tab-image-queue/', views.tab_image_queue, name='tab_image_queue'),    
    path('admin/tab-match-by-name/', views.tab_match_by_name, name='tab_match_by_name'), 
    path('admin/tab-match-by-barcode/', views.tab_match_by_barcode, name='tab_match_by_barcode'),   
    path('admin/bulk-upload/', views.bulk_upload_view, name='bulk_upload'),
    path('admin/bulk-upload/process/', views.process_excel_upload, name='process_excel_upload'),
    path('admin/image-matcher/', views.matcher_dashboard, name='matcher_dashboard'),
    path('admin/image-matcher/finalize/', views.finalize_match, name='finalize_match'),
    path('admin/image-matcher/skip/<uuid:product_id>/', views.skip_product, name='skip_product'),


    path('admin/', admin.site.urls),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),# schema generation
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),# Swagger UI
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),# Redoc
    path('tinymce/', include('tinymce.urls')),# tinymce

    path('admin/dashboard-stats/', admin_dashboard_stats, name='admin_dashboard_stats'),



    path('account/', include('accounts.urls')),
    path('', include('products.urls')),
    path('merchant-products/', include('merchant.urls')),
    path('services/', include('services.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

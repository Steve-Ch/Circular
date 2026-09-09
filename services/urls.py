from django.urls import path
from . import views

urlpatterns = [
    path('services/available/', views.AvailableServicesView.as_view(), name='available-services'),
    path('services/request/', views.InitiateServiceRequestView.as_view(), name='initiate-request'),
]
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction as db_transaction
from .models import EstateService, ServiceRequest
from .serializers import AvailableEstateServiceSerializer, ServiceRequestSerializer
from products.utils import initiate_payment 

class AvailableServicesView(generics.ListAPIView):
    """Returns services actively available in the logged-in user's estate."""
    serializer_class = AvailableEstateServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.estate:
            return EstateService.objects.none()
        
        return EstateService.objects.filter(
            estate=user.estate,
            is_available=True
        )

class InitiateServiceRequestView(generics.CreateAPIView):
    """Creates a service request, a transaction, and returns the Paystack checkout URL."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        user = request.user
        estate_service_id = request.data.get('estate_service_id')
        notes = request.data.get('notes', '')
        callback_url = request.data.get('callback_url', '')
        if not callback_url:
            return Response(
                {"error": "callback_url is required"}, 
                status=status.HTTP_400_BAD_REQUEST
                )


        try:
            estate_service = EstateService.objects.get(
                id=estate_service_id, 
                estate=user.estate, 
                is_available=True
            )
        except EstateService.DoesNotExist:
            return Response(
                {"error": "Service not found or unavailable in your estate."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        with db_transaction.atomic():
            # 1. Create the Transaction
            txn = Transaction.objects.create(
                user=user,
                amount=estate_service.request_fee,
                status=Transaction.Status.PENDING,
                payment_type=Transaction.Type.SERVICE
            )

            # 2. Create the Service Request
            service_req = ServiceRequest.objects.create(
                resident=user,
                estate_service=estate_service,
                status=ServiceRequest.StatusChoices.PENDING,
                fee_paid=estate_service.request_fee,
                notes=notes,
                transaction=txn # Link the transaction here
            )

        # 3. Call Paystack
        pay_res = initiate_payment(
            amount=txn.amount, 
            email=user.email, 
            reference=txn.reference, 
            callback_url=callback_url
        )

        # return Response({
        #     "message": "Payment initiated successfully.",
        #     "payment_data": payment_response,
        #     "service_request_id": service_req.id
        # }, status=status.HTTP_201_CREATED)

        if pay_res.get('status'):
            data = {
                "reference": txn.reference,
                "amount": txn.amount,
                "status": txn.status,
                "checkout_url": pay_res['data']['authorization_url']
            }
            return Response(self.get_serializer(data).data, status=status.HTTP_201_CREATED)
        
        return Response({
            "error": "Payment failed",
            "data": pay_res,
            }, status=status.HTTP_400_BAD_REQUEST)
    
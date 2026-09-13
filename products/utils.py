from django.conf import settings
from django.contrib.auth import get_user_model
import requests
import requests
from .models import Transaction, Order, OrderItem
from merchant.models import MerchantProduct
from website.models import SiteConfiguration
from django.db import transaction as db_transaction
from .models import Transaction
from services.models import ServiceRequest
from products.models import Order
from accounts.utils import send_html_mail



def initiate_payment(amount, email, reference, callback_url= None):
        key = settings.PAYSTACK_SECRET_KEY
        if SiteConfiguration.get_solo().test_mode:
            key = settings.PAYSTACK_SECRET_KEY_TEST
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        data = {
            "email": email,
            "amount": int(amount * 100),
            "reference": reference,
            "callback_url": callback_url,
        }

        response = requests.post(
            f"{settings.PAYSTACK_BASE_URL}/transaction/initialize",
            json=data,
            headers=headers
        ).json()
        return response




def paystack_verify(reference):
    """
    Verifies a transaction using the Paystack reference.
    Returns the JSON response from Paystack.
    """
    # The reference is passed as a path parameter in the URL
    url = f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}"
    
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Optional: raises an error for 4xx/5xx responses
        print(response.json())
        return response.json()
        # return response.json()
    except requests.exceptions.RequestException as e:
        # Log the error or handle it as needed
        return {"status": False, "message": str(e)}








def finalize_order(ref, status):
    if status == 'success':
        # Use select_for_update() to wait for other transactions to finish
        with db_transaction.atomic():
            transaction = Transaction.objects.select_for_update().get(reference=ref)
            
            if transaction.status == Transaction.Status.PENDING:
                user = transaction.user
                cart_items = user.cart.items.select_related('merchant_product').all()
                
                order = Order.objects.create(
                    user=user,
                    transaction=transaction,
                    status=Order.Status.PENDING,
                    full_name=f"{user.first_name} {user.last_name}",
                    email=user.email,
                    estate = user.estate,
                    address=user.address,
                )

                order_items = []
                for item in cart_items:
                    merchant_product = MerchantProduct.objects.get(id=item.merchant_product.id)         
                    order_items.append(
                        OrderItem(
                            order=order,
                            merchant_product=merchant_product,
                            quantity=item.quantity,
                            price_at_purchase=merchant_product.price,
                            product_name = merchant_product.product.name,
                        )
                    )

                OrderItem.objects.bulk_create(order_items)
                cart_items.delete()
                
                transaction.status = Transaction.Status.SUCCESSFUL
                transaction.save()
                
                if user.eligible_for_free_delivery:
                    user.eligible_for_free_delivery = False
                    user.save(update_fields=['eligible_for_free_delivery'])

                # 1. Fetch all active users belonging to the 'Rider' group
                rider_emails = list(
                    get_user_model().objects.filter(
                        groups__name='Rider', 
                        is_active=True
                    ).values_list('email', flat=True)
                )
                
                # 3. Call your function passing the list of emails directly into the first argument
                if rider_emails:

                    subject = f"🚨 New Delivery Request Available - Ref: {transaction.reference}"
                    
                    message = (
                        f"A new order has been placed by {order.full_name}. "
                        f"Order Total: NGN {order.price_total}. Reference: {transaction.reference}. "
                        f"Please log in to your dashboard immediately to start this delivery."
        )


                    send_html_mail(
                        email=rider_emails,  # Passing the list here
                        subject=subject,
                        message=message,
                        title='New Order Alert',
                        support=False,
                    )
                else:
                    print("No active users found in the Rider group.")





def finalize_service_request(ref, status):
    """Marks request as PAID and alerts the provider via WhatsApp."""
    if status == 'success':
        with db_transaction.atomic():
            txn = Transaction.objects.select_for_update().get(reference=ref)
            
            if txn.status == Transaction.Status.PENDING and txn.payment_type == Transaction.Type.SERVICE:
                
                # Update Transaction
                txn.status = Transaction.Status.SUCCESSFUL
                txn.save()

                # Update Service Request
                service_req = txn.service_request
                service_req.status = ServiceRequest.StatusChoices.PAID
                service_req.save()

                # Dispatch WhatsApp Message
                provider = service_req.estate_service.provider
                resident = service_req.resident
                
                msg = (
                    # f"🔔 *New Service Request!*\n\n"
                    f"Service: {service_req.estate_service.service.name}\n"
                    f"Resident: {resident.full_name}\n"
                    f"Phone: {resident.phone_number}\n"
                    f"Address: {resident.address}, {resident.estate.name}\n"
                    f"Notes: {service_req.notes or 'None'}\n\n"
                    f"Please contact the resident to proceed."
                )
                
                # Run this asynchronously (e.g., Celery) in production so it doesn't block the webhook response
                # send_whatsapp_message(provider.phone, msg)

            
                send_html_mail(
                    email= provider.email,  # Passing the list here
                    subject='🔔 New Service Request!',
                    message=msg,
                    title='New Service Request!',
                    support=False,
                    )

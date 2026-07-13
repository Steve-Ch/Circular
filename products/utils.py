from django.conf import settings
from django.contrib.auth import get_user_model
import requests
import requests
from .models import Transaction, Cart, Order, OrderItem
from django.db import transaction 






# def finalize_order(user, transaction_obj):
#     # We use atomic() to ensure that if any step fails, 
#     # the cart isn't emptied and the order isn't half-created.
#     with transaction.atomic():
#         cart = user.cart
#         cart_items = cart.items.all()

#         # 1. Create the Order instance
#         # (Assuming you get address/full_name from a saved profile or the request)
#         order = Order.objects.create(
#             user=user,
#             reference=transaction_obj.reference,
#             status=Order.Status.PAID,
#             full_name=f"{user.first_name} {user.last_name}",
#             email=user.email,
#             address="User Address" # Pull this from your checkout data
#         )

#         # 2. Bulk create OrderItems
#         # We prepare a list of OrderItem objects in memory first (more efficient)
#         order_items = [
#             OrderItem(
#                 order=order,
#                 product=item.product,
#                 quantity=item.quantity,
#                 price_at_purchase=item.product.price # Capturing price NOW
#             )
#             for item in cart_items
#         ]
        
#         # Save all items to DB in one query
#         OrderItem.objects.bulk_create(order_items)

#         # 3. Now clear the cart
#         cart_items.delete()

#         return order





def initiate_payment(amount, email, reference, callback_url):
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
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





from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from django.db.models import F
from products.models import Product, Order
from accounts.utils import send_html_mail

def finalize_order(ref, status):
    if status == 'success':
        # Use select_for_update() to wait for other transactions to finish
        with db_transaction.atomic():
            transaction = Transaction.objects.select_for_update().get(reference=ref)
            
            if transaction.status == Transaction.Status.PENDING:
                user = transaction.user
                cart_items = user.cart.items.select_related('product').all()
                
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
                    product = Product.objects.get(id=item.product.id)

                    # LOCK the product row so nobody else can change its quantity right now
                    # product = Product.objects.select_for_update().get(id=item.product.id)
                    
                    # if product.quantity < item.quantity:
                    #     # This triggers the rollback of the transaction.atomic()
                    #     raise ValidationError(f"Stock ran out for {product.name} during payment.")

                    # Use F expression to avoid Python-level race conditions
                    # product.quantity = F('quantity') - item.quantity
                    # product.save()
                    
                    # Refresh from DB to get the current price for order_items
                    # product.refresh_from_db() 
                    
                    order_items.append(
                        OrderItem(
                            order=order,
                            product=product,
                            quantity=item.quantity,
                            price_at_purchase=product.price,
                            product_name = product.name,
                        )
                    )

                OrderItem.objects.bulk_create(order_items)
                cart_items.delete()
                
                transaction.status = Transaction.Status.SUCCESSFUL
                transaction.save()




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




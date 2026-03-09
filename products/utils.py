from django.conf import settings
from django.contrib.auth import get_user_model
import requests
import requests
from .models import Transaction, Cart, Order, OrderItem
from django.contrib.auth import get_user_model
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





def initiate_payment(amount, email, reference):
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        data = {
            "email": email,
            "amount": int(amount * 100),
            "reference": reference,
            "callback_url": settings.CALLBACK_URL,
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

def finalize_order(ref, status):
    if status == 'success':
        transaction = Transaction.objects.get(reference=ref)
        
        if transaction.status == Transaction.Status.PENDING:
            transaction.status = Transaction.Status.SUCCESSFUL
            user = transaction.user
            
            # Use db_transaction.atomic to ensure all-or-nothing
            with db_transaction.atomic():
                cart = user.cart
                cart_items = cart.items.all()
                
                # 1. Create the Order instance
                order = Order.objects.create(
                    user=user,
                    reference=transaction.reference,
                    status=Order.Status.PAID,
                    full_name=f"{user.first_name} {user.last_name}",
                    email=user.email,
                    address=user.address
                )

                order_items = []
                for item in cart_items:
                    product = item.product
                    
                    # --- NEW LOGIC: Deduct Inventory ---
                    if product.quantity < item.quantity:
                        raise ValidationError(f"Insufficient stock for {product.name}")
                    
                    product.quantity -= item.quantity
                    product.save()
                    # -----------------------------------

                    # Prepare OrderItem
                    order_items.append(
                        OrderItem(
                            order=order,
                            product=product,
                            quantity=item.quantity,
                            price_at_purchase=product.price
                        )
                    )

                # 2. Bulk create OrderItems
                OrderItem.objects.bulk_create(order_items)

                # 3. Now clear the cart
                cart_items.delete()
                
                # Save the transaction status change
                transaction.save()


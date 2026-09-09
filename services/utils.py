import requests
from django.conf import settings
from django.db import transaction as db_transaction
from products.models import Transaction, ServiceRequest

# def send_whatsapp_message(provider_phone, message_body):
#     """Sends a text message using Meta's WhatsApp Cloud API."""
#     url = f"https://graph.facebook.com/v17.0/{settings.WA_PHONE_NUMBER_ID}/messages"
#     headers = {
#         "Authorization": f"Bearer {settings.WA_ACCESS_TOKEN}",
#         "Content-Type": "application/json"
#     }
    
#     # Format phone number (Meta requires country code without the '+' sign)
#     clean_phone = str(provider_phone).replace("+", "").strip()
    
#     data = {
#         "messaging_product": "whatsapp",
#         "to": clean_phone,
#         "type": "text",
#         "text": {"body": message_body}
#     }
#     try:
#         requests.post(url, headers=headers, json=data)
#     except Exception as e:
#         print(f"WhatsApp message failed: {e}")

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
                    f"🔔 *New Service Request!*\n\n"
                    f"*Service:* {service_req.estate_service.service.name}\n"
                    f"*Resident:* {resident.full_name}\n"
                    f"*Phone:* {resident.phone_number}\n"
                    f"*Address:* {resident.address}, {resident.estate.name}\n"
                    f"*Notes:* {service_req.notes or 'None'}\n\n"
                    f"Please contact the resident to proceed."
                )
                
                # Run this asynchronously (e.g., Celery) in production so it doesn't block the webhook response
                # send_whatsapp_message(provider.phone, msg)


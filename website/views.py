import datetime
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required

from products.models import Order
from accounts.models import User
# Import your Estate and Merchant models here, e.g.:
from accounts.models import Estate
from merchant.models import Merchant

@staff_member_required
def admin_dashboard_stats(request):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    today = timezone.now().date()
    
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else today
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else today
    except (ValueError, TypeError):
        start_date = today
        end_date = today

    start_datetime = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min))
    end_datetime = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max))

    # 1. User metrics
    total_users = User.objects.count()
    new_users = User.objects.filter(date_joined__range=(start_datetime, end_datetime)).count()

    # 2. Additional metrics (Replace counts with your actual model counts)
    supported_estates = Estate.objects.count()
    onboarded_merchants = Merchant.objects.count()

    # 3. Successful Deliveries & Profit Calculation
    successful_orders = Order.objects.filter(
        status=Order.Status.DELIVERED,
        created_at__range=(start_datetime, end_datetime)
    ).prefetch_related('items').select_related('transaction')

    deliveries_count = successful_orders.count()

    total_delivery_profit = 0
    for order in successful_orders:
        items_total = sum([
            (item.price_at_purchase * item.quantity) 
            for item in order.items.all() if item.price_at_purchase
        ])
        
        if order.transaction and order.transaction.amount:
            delivery_fee = float(order.transaction.amount) - float(items_total)
            if delivery_fee > 0:
                total_delivery_profit += delivery_fee

    return JsonResponse({
        'total_users': total_users,
        'new_users': new_users,
        'supported_estates': supported_estates,
        'onboarded_merchants': onboarded_merchants,
        'successful_deliveries': deliveries_count,
        'delivery_profit': round(total_delivery_profit, 2)
    })
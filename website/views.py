import datetime
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from products.models import Order,Category
from accounts.models import User
# Import your Estate and Merchant models here, e.g.:
from accounts.models import Estate
from merchant.models import Merchant
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from .models import UnlinkedImage
from products.models import Product, ProductImage
from .services import process_zip_images
from django.http import HttpResponse
# from .servicies_api import fetch_open_food_facts_image
from django.core.files.base import ContentFile
import requests
import pandas as pd
from django.core.files.storage import FileSystemStorage
import os
import traceback



@staff_member_required
def bulk_upload_view(request):
    """Admin view handling multi-format spreadsheet/text uploads and camera ZIP archives."""
    if request.method == "POST":
        spreadsheet_file = request.FILES.get("spreadsheet_file")
        zip_file = request.FILES.get("zip_file")

        if not spreadsheet_file and not zip_file:
            messages.error(request, "Please select at least one file to upload.")
            return redirect("bulk_upload")

        # 1. Process ZIP File
        if zip_file:
            try:
                img_count = process_zip_images(zip_file)
                messages.success(request, f"Successfully staged {img_count} images for matching.")
            except Exception as e:
                traceback.print_exc() 
                messages.error(request, f"Error processing ZIP archive: {str(e)}")

        # 2. Process Spreadsheet / Text File (.xlsx, .xls, .csv, .tsv, .txt)
        if spreadsheet_file:
            fs = FileSystemStorage()
            filename = fs.save(f"tmp_{spreadsheet_file.name}", spreadsheet_file)
            filepath = fs.path(filename)
            
            new_cats = []
            try:
                df = read_tabular_file(filepath)
                # Normalize column names
                df.columns = df.columns.str.lower().str.strip()
                
                col_name = 'category' if 'category' in df.columns else None
                excel_categories = set()
                
                if col_name:
                    for cat_str in df[col_name].unique():
                        if cat_str:
                            # Enforce Title Case on Excel Categories
                            cats = [c.strip().title() for c in str(cat_str).split(',') if c.strip()]
                            excel_categories.update(cats)
                
                # Fetch existing categories and compare in lowercase to prevent case-based duplicates
                existing_cats_lower = {c.lower() for c in Category.objects.values_list('name', flat=True)}
                
                # Only offer categories that don't exist in the database yet
                new_cats_set = {c for c in excel_categories if c.lower() not in existing_cats_lower}
                new_cats = sorted(list(new_cats_set))

            except Exception as e:
                traceback.print_exc() 
                messages.error(request, f"Error reading upload file: {str(e)}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect("bulk_upload")

            if new_cats:
                request.session['tmp_excel_path'] = filepath
                return render(request, "admin/image_matcher/category_preview.html", {"new_cats": new_cats})
            else:
                return process_excel_data(request, filepath, [])

        if not spreadsheet_file and zip_file:
            return redirect("bulk_upload")

    return render(request, "admin/bulk_upload.html")

def process_excel_upload(request):
    """Receives selected categories from step 2 and initiates database processing."""
    if request.method == "POST":
        filepath = request.session.get('tmp_excel_path')
        selected_new_cats = request.POST.getlist('categories_to_create')
        
        if filepath and os.path.exists(filepath):
            return process_excel_data(request, filepath, selected_new_cats)
        else:
            messages.error(request, "Session expired or file missing. Please re-upload.")
            
    return redirect('bulk_upload')


def process_excel_data(request, filepath, selected_new_cats):
    """Executes O(1) bulk creates and updates across any supported file format."""
    try:
        # 1. Bulk Create Selected Categories (Applying .title() here mimics your save() method)
        if selected_new_cats:
            cats_to_create = [Category(name=cat.strip().title()) for cat in selected_new_cats]
            Category.objects.bulk_create(cats_to_create, ignore_conflicts=True)

        # Case-insensitive map of all categories in DB
        cat_map = {c.name.lower(): c for c in Category.objects.all()}

        # 2. Parse file
        df = read_tabular_file(filepath)
        df.columns = df.columns.str.lower().str.strip()

        # Force Title Case on Excel names to match the DB naming convention
        excel_names = [str(n).strip().title() for n in df['name'].tolist() if str(n).strip()]
        
        # O(1) Pre-fetches
        existing_products = Product.objects.filter(name__in=excel_names)
        existing_map = {p.name.lower(): p for p in existing_products}
        
        # Pre-fetch existing barcodes to prevent DB clashes
        db_barcodes = {b: n.lower() for b, n in Product.objects.exclude(barcode__isnull=True).values_list('barcode', 'name')}
        seen_barcodes = set()

        new_products = []
        update_products = []
        product_category_relations = []

        for _, row in df.iterrows():
            # Applying .title() here mimics your save() method for Products
            name = str(row.get('name', '')).strip().title()
            if not name:
                continue
            
            p_lower = name.lower()
            desc = str(row.get('description', '')).strip()
            cat_str = str(row.get('category', '')).strip()
            
            # --- EXTRACT PRICE ---
            raw_price = str(row.get('price', '')).strip()
            try:
                price = float(raw_price) if raw_price else 0.00
            except (ValueError, TypeError):
                price = 0.00
            
            # --- BARCODE SANITIZATION ---
            raw_barcode = str(row.get('barcode', '')).strip()
            barcode = raw_barcode if raw_barcode else None
            
            if barcode:
                if barcode in seen_barcodes:
                    barcode = None
                elif barcode in db_barcodes and db_barcodes[barcode] != p_lower:
                    barcode = None
                else:
                    seen_barcodes.add(barcode)

            # Case-insensitive category matching
            cats_for_product = []
            if cat_str:
                for c_name in cat_str.split(','):
                    c_name_clean = c_name.strip().lower()
                    if c_name_clean in cat_map:
                        cats_for_product.append(cat_map[c_name_clean])

            if p_lower in existing_map:
                p = existing_map[p_lower]
                needs_update = False
                
                if desc and p.description != desc: 
                    p.description = desc
                    needs_update = True
                    
                if barcode and p.barcode != barcode:
                    p.barcode = barcode
                    needs_update = True
                
                if price and p.price != price:
                    p.price = price
                    needs_update = True
                    
                if needs_update:
                    update_products.append(p)
                    
                if cats_for_product:
                    product_category_relations.append((p, cats_for_product))
            else:
                # 'name' is already safely Title Cased at the start of the loop
                new_p = Product(
                    name=name, 
                    description=desc, 
                    barcode=barcode, 
                    price=price,
                    display=False
                )
                new_products.append(new_p)
                if cats_for_product:
                    product_category_relations.append((new_p, cats_for_product))

        # 3. Database Updates
        if new_products:
            Product.objects.bulk_create(new_products, ignore_conflicts=True)
            
        if update_products:
            Product.objects.bulk_update(update_products, ['description', 'barcode', 'price'])

        # 4. Many-to-Many Relationships (Categories)
        all_processed_products = Product.objects.filter(name__in=excel_names)
        processed_map = {p.name.lower(): p for p in all_processed_products}
        
        ProductCategoryThrough = Product.categories.through
        m2m_inserts = []
        
        for prod_ref, categories in product_category_relations:
            real_prod = processed_map.get(prod_ref.name.lower())
            if real_prod:
                for cat in categories:
                    m2m_inserts.append(ProductCategoryThrough(product_id=real_prod.id, category_id=cat.id))
                    
        if m2m_inserts:
            ProductCategoryThrough.objects.bulk_create(m2m_inserts, ignore_conflicts=True)

        messages.success(request, f"Processed {len(df)} rows: {len(new_products)} created, {len(update_products)} updated.")

    except Exception as e:
        traceback.print_exc()
        messages.error(request, f"Error processing database updates: {str(e)}")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    return redirect('matcher_dashboard')


def read_tabular_file(filepath):
    """Dynamically parses Excel (.xlsx, .xls), CSV (.csv), TSV (.tsv), and Text (.txt) files."""
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext in ['.xlsx', '.xls']:
        return pd.read_excel(filepath).fillna('')
    else:
        # Handles .csv, .tsv, .txt by auto-detecting separators (commas, tabs, pipes)
        try:
            return pd.read_csv(filepath, sep=None, engine='python').fillna('')
        except Exception:
            return pd.read_excel(filepath).fillna('')


# --- Helper Function for the API ---
def fetch_open_food_facts_image(barcode):
    # Ensure barcode is stripped of any accidental whitespace or symbols
    clean_barcode = str(barcode).strip()
    url = f"https://world.openfoodfacts.org/api/v2/product/{clean_barcode}.json"
    
    headers = {
        'User-Agent': 'YourAppName - Web/Django - Version 1.0 (contact: your-email@example.com)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        
        # 1. Catch 404 right away so it doesn't trigger your error print block
        if response.status_code == 404:
            print(f"Barcode {clean_barcode} is not in the Open Food Facts database.")
            return None
            
        # Catch any other unexpected server error codes (e.g., 500, 503)
        if response.status_code != 200:
            print(f"API returned an error code: {response.status_code}")
            return None
            
        data = response.json()
        if data.get('status') == 1:
            return data['product'].get('image_url')
            
    except requests.exceptions.Timeout:
        print(f"Skipping barcode {clean_barcode}: Open Food Facts API timed out.")
    except requests.exceptions.JSONDecodeError:
        print("Failed to decode JSON. The API sent back HTML/Text instead.")
    except Exception as e:
        print(f"Error getting the image: {e}")
        
    return None


# --- Fixed Skip View ---
def skip_product(request, product_id):
    """Stores the skipped product ID as a string in the session."""
    if request.method == "POST":
        active_tab = request.POST.get("active_tab", "name")
        
        # Convert UUID to string to fix JSON serialization error!
        product_id_str = str(product_id) 
        
        skipped = request.session.get('skipped_products', [])
        if product_id_str not in skipped:
            skipped.append(product_id_str)
            request.session['skipped_products'] = skipped
            
        messages.info(request, "Product skipped for this session.")
        return redirect(f"/admin/image-matcher/?tab={active_tab}")
    return redirect("/admin/image-matcher/")


# --- Barcode View with Subtabs ---
def tab_match_by_barcode(request):
    """Finds a product with a barcode, handling both API and Clipboard methods."""
    subtab = request.GET.get('sub', 'api') # Default to API
    skipped_ids = request.session.get('skipped_products', [])
    
    # Fix: Explicitly exclude both null and empty string barcodes
    product = Product.objects.annotate(img_count=Count('images'))\
                             .filter(img_count=0)\
                             .exclude(barcode__isnull=True)\
                             .exclude(barcode__exact='')\
                             .exclude(id__in=skipped_ids)\
                             .first()
                             
    categories = Category.objects.all().order_by('name')
    image_url = None
    
    if product and subtab == 'api':
        image_url = fetch_open_food_facts_image(product.barcode)

    return render(request, "admin/image_matcher/tabs/tab_barcode.html", {
        "product": product, "categories": categories, 
        "subtab": subtab, "image_url": image_url
    })

# --- Updated Finalize Match ---
def finalize_match(request):
    """Handles Zip images, pasted files, pasted URLs, OR Open Food Facts API URLs."""
    if request.method == "POST":
        product = get_object_or_404(Product, id=request.POST.get("product_id"))
        selected_cats = request.POST.getlist("categories")
        
        # Pull description, defaulting to empty string if missing
        description = request.POST.get("description", "").strip()
        active_tab = request.POST.get("active_tab", "queue")
        
        # Enforce compulsory fields ONLY if not already present on the product
        if not selected_cats and not product.categories.exists():
            messages.error(request, f"Match Failed: {product.name} requires at least one category.")
            return redirect(f"/admin/image-matcher/?tab={active_tab}")

        unlinked_id = request.POST.get("unlinked_id")
        pasted_file = request.FILES.get("pasted_file")
        pasted_url = request.POST.get("pasted_url")
        api_image_url = request.POST.get("api_image_url") 

        if unlinked_id:
            unlinked = get_object_or_404(UnlinkedImage, id=unlinked_id)
            ProductImage.objects.create(product=product, image=unlinked.image.file)
            unlinked.delete()
        elif pasted_file:
            ProductImage.objects.create(product=product, image=pasted_file)
        elif pasted_url or api_image_url:
            target_url = pasted_url if pasted_url else api_image_url
            target_url = target_url.strip()
            
            # FIX 1: Add https if the API omitted the schema
            if target_url.startswith('//'):
                target_url = 'https:' + target_url
                
            try:
                # FIX 2: Add a User-Agent so the CDN doesn't block the request
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(target_url, headers=headers, stream=True, timeout=10)
                
                if response.status_code == 200:
                    ext = target_url.split('?')[0].split('.')[-1][:4]
                    if not ext.isalnum():
                        ext = 'jpg'
                    img_file = ContentFile(response.content, name=f"downloaded_image.{ext}")
                    ProductImage.objects.create(product=product, image=img_file)
                else:
                    messages.error(request, f"Failed to download image. Server returned status: {response.status_code}")
                    return redirect(f"/admin/image-matcher/?tab={active_tab}")
            except Exception as e:
                # This prints the exact error to your terminal so you can see what went wrong
                print(f"Download Error: {e}") 
                messages.error(request, "Invalid image URL provided or the image server blocked the request.")
                return redirect(f"/admin/image-matcher/?tab={active_tab}")

        # Update categories if provided
        if selected_cats:
            product.categories.set(selected_cats)
        
        # Always save the description if one is provided.
        if description:
            product.description = description

        product.display = True
        product.save()
        messages.success(request, f"Successfully matched {product.name}!")
        
        return redirect(f"/admin/image-matcher/?tab={active_tab}")

def tab_match_by_name(request):
    """Finds a product without an image, entirely relying on frontend clipboard logic."""
    skipped_ids = request.session.get('skipped_products', [])
    product = Product.objects.annotate(img_count=Count('images'))\
                             .filter(img_count=0)\
                             .exclude(id__in=skipped_ids)\
                             .first()
    
    categories = Category.objects.all().order_by('name')
        
    return render(request, "admin/image_matcher/tabs/tab_name.html", {
        "product": product, "categories": categories
    })


def matcher_dashboard(request):
    """Main shell. Reads ?tab= to remember where the user was."""
    active_tab = request.GET.get('tab', 'queue')
    unmatched_total = Product.objects.annotate(img_count=Count('images')).filter(img_count=0).count()
    return render(request, "admin/image_matcher/dashboard.html", {
        "active_tab": active_tab,
        "unmatched_total": unmatched_total
    })

# --- TAB 1: Match By Image (Queue) ---
def tab_image_queue(request):
    unlinked = UnlinkedImage.objects.first()
    categories = Category.objects.all().order_by('name')
    return render(request, "admin/image_matcher/tabs/tab_queue.html", {"unlinked": unlinked, "categories": categories})



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


@staff_member_required
def matcher_base(request):
    """Renders the main Jazzmin shell and HTMX container."""
    return render(request, "admin/image_matcher/base.html")


# --- MODE 1: MATCH BY IMAGE ---
@staff_member_required
def get_next_matcher_board(request):
    unlinked_image = UnlinkedImage.objects.first()
    if not unlinked_image:
        return render(request, "admin/image_matcher/partials/empty_queue.html")
    
    return render(request, "admin/image_matcher/partials/board_by_image.html", {
        "unlinked": unlinked_image, 
    })

def search_unlinked_products(request):
    """Returns HTMX search results."""
    q = request.GET.get("q", "")
    unlinked_id = request.GET.get("unlinked_id")
    products = Product.objects.filter(display=False, name__icontains=q)[:10] if len(q) >= 2 else []
    return render(request, "admin/image_matcher/partials/search_results.html", {
        "products": products, "unlinked_id": unlinked_id
    })

def preview_match(request, product_id, unlinked_id):
    """Renders the Confirmation Panel with existing categories highlighted."""
    product = get_object_or_404(Product, id=product_id)
    unlinked = get_object_or_404(UnlinkedImage, id=unlinked_id)
    all_categories = Category.objects.all().order_by('name')
    
    return render(request, "admin/image_matcher/partials/confirm_match.html", {
        "product": product,
        "unlinked": unlinked,
        "all_categories": all_categories
    })

def skip_image(request, unlinked_id):
    """Standard POST to push image to the back of the queue."""
    if request.method == "POST":
        unlinked = get_object_or_404(UnlinkedImage, id=unlinked_id)
        from django.utils import timezone
        unlinked.sort_order = timezone.now()
        unlinked.save()
        messages.info(request, f"Skipped {unlinked.filename} for now.")
    return redirect('matcher_dashboard')

@staff_member_required
def link_image_to_product(request):
    """Standard POST to finalize the match with strict category validation."""
    if request.method == "POST":
        unlinked = get_object_or_404(UnlinkedImage, id=request.POST.get("unlinked_id"))
        product = get_object_or_404(Product, id=request.POST.get("product_id"))
        selected_cats = request.POST.getlist("categories")

        # Fix: Compulsory category check only if empty
        if not selected_cats and not product.categories.exists():
            messages.error(request, f"Match Failed: You must select at least one category for {product.name}.")
            return redirect('matcher_dashboard')

        ProductImage.objects.create(product=product, image=unlinked.image.file)

        if selected_cats:
            product.categories.set(selected_cats)
        
        product.display = True
        product.save()
        unlinked.delete()
        messages.success(request, f"Successfully matched image to {product.name}!")

    return redirect('matcher_dashboard')

# --- MODE 2: MATCH BY PRODUCT ---
@staff_member_required
def match_by_product_list(request):
    search_query = request.GET.get('q', '')
    page_num = int(request.GET.get('page', 1))

    qs = Product.objects.annotate(img_count=Count('images')).filter(img_count=0)
    if search_query:
        qs = qs.filter(name__icontains=search_query)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(page_num)
    categories = Category.objects.all().order_by('name')

    context = {"products": page_obj, "search_query": search_query, "categories": categories}

    # If this is an HTMX pagination request, ONLY return the rows, not the whole page.
    if request.headers.get('HX-Request') == 'true' and page_num > 1:
        return render(request, "admin/image_matcher/partials/product_rows.html", context)

    # Otherwise, return the full list container
    return render(request, "admin/image_matcher/partials/product_list.html", context)
@staff_member_required
def direct_upload_to_product(request, product_id):
    """Standard POST file upload."""
    if request.method == "POST":
        product = get_object_or_404(Product, id=product_id)
        uploaded_file = request.FILES.get("direct_image")
        selected_cat = request.POST.get("category")

        if not product.categories.exists() and not selected_cat:
            messages.error(request, f"Failed: {product.name} needs a category.")
            return redirect('matcher_dashboard')

        if uploaded_file:
            ProductImage.objects.create(product=product, image=uploaded_file)
            if selected_cat:
                product.categories.add(selected_cat)
            product.display = True
            product.save()
            messages.success(request, f"Uploaded image for {product.name}.")
            
    return redirect('matcher_dashboard')
import os
import sys
import django
from django.db.models import Count, functions

# 1. Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

# 2. Import the Product model
from products.models import Product

def find_case_insensitive_duplicates():
    print("Searching for duplicate product names (case-insensitive)...")
    
    # Group products by lowercase name and count occurrences
    duplicates = (
        Product.objects.annotate(lower_name=functions.Lower('name'))
        .values('lower_name')
        .annotate(name_count=Count('id'))
        .filter(name_count__gt=1)
    )
    
    if not duplicates:
        print("🎉 No duplicate product names found!")
        return

    print(f"Found {len(duplicates)} unique names that have duplicates.\n")
    print(f"{'ID':<8} | {'PRODUCT NAME'}")
    print("-" * 50)
    
    # Retrieve and print all individual products matching the duplicate names
    for entry in duplicates:
        lower_name = entry['lower_name']
        matching_products = Product.objects.filter(name__iexact=lower_name)
        
        for product in matching_products:
            print(f"{product.id:<8} | {product.name}")
        print("-" * 50) # Separation line between different groups of duplicates

if __name__ == "__main__":
    find_case_insensitive_duplicates()

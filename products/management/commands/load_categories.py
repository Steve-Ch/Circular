from django.core.management.base import BaseCommand
from products.models import Category

class Command(BaseCommand):
    help = 'Load fixed categories into the database'

    def handle(self, *args, **kwargs):
        categories = [
            "Appliances", "home & Kitchen", "Home", "Men's Fasion",
            "Women's Fasion", "Kid's Fasion", "Watches", "Luggage & Travel Gear", "Makeup", "Fregrances", "Hair Care", 
            "Personal Care", "Oral Care", "Health Care", "Beer, Wine& Spirits", "Food Cupboard", "Household Cleaning", 
            "Training Equipment", "Accessories", "Sports", "Dipering", "Baby & Toddler Toys", "Home", 
        ]

 


        for name in categories:
            Category.objects.get_or_create(name=name)

        self.stdout.write(self.style.SUCCESS('Categories loaded successfully!'))

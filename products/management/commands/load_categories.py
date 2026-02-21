from django.core.management.base import BaseCommand
from products.models import Category

class Command(BaseCommand):
    help = 'Load fixed categories into the database'

    def handle(self, *args, **kwargs):
        categories = [
            'Home & Office', 'Phones & Tablets', 'Fasion', 
            'Health & Beauty', 'Electronics', 'Computing', 'Grocery',
            'Garden & outdoors', 'Automobile', 'Sporting Goods', 'Gaming', 'Baby Products'
        ]

 


        for name in categories:
            Category.objects.get_or_create(name=name)

        self.stdout.write(self.style.SUCCESS('Categories loaded successfully!'))

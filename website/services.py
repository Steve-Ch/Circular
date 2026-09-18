# services.py
import os
import zipfile
import pandas as pd
from django.core.files.base import ContentFile
from products.models import Product, Category
from .models import UnlinkedImage
import io
from django.core.files.storage import FileSystemStorage


def process_zip_images(zip_file_obj):
    """
    Extracts camera photos from a ZIP archive directly into the UnlinkedImage staging area.
    """
    unlinked_instances = []
    
    with zipfile.ZipFile(zip_file_obj, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            # Skip hidden files and subdirectories
            if file_info.is_dir() or file_info.filename.startswith('__MACOSX'):
                continue
                
            ext = os.path.splitext(file_info.filename)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                filename = os.path.basename(file_info.filename)
                file_content = zip_ref.read(file_info.filename)
                
                unlinked = UnlinkedImage(filename=filename)
                unlinked.image.save(filename, ContentFile(file_content), save=False)
                unlinked_instances.append(unlinked)

    if unlinked_instances:
        UnlinkedImage.objects.bulk_create(unlinked_instances, batch_size=1000)

    return len(unlinked_instances)
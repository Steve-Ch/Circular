
import requests
from django.conf import settings
from django.core.files.base import ContentFile

def fetch_google_images(query):
    """Fetches up to 10 image URLs using Google Custom Search API without Captchas."""
    # Note: Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX in your settings.py
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'cx': settings.GOOGLE_SEARCH_CX,
        'key': settings.GOOGLE_SEARCH_API_KEY,
        'searchType': 'image',
        'num': 10
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            return [item['link'] for item in response.json().get('items', [])]
    except Exception:
        pass
    return []

def fetch_open_food_facts_image(barcode):
    """Fetches the primary image URL from Open Food/Beauty Facts."""
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('status') == 1:
            return data['product'].get('image_url')
    except Exception as e:
            print(f"Error getting the image: {e}")
            pass
    return None

def download_image_to_django(image_url):
    """Downloads an external URL into a Django ContentFile for saving."""
    try:
        response = requests.get(image_url, stream=True, timeout=10)
        if response.status_code == 200:
            # Extract extension or default to .jpg
            ext = image_url.split('.')[-1][:4] if '.' in image_url[-5:] else 'jpg'
            return ContentFile(response.content, name=f"api_download.{ext}")
    except Exception as e:
        print(f"Error downloading image: {e}")
        pass
    return None
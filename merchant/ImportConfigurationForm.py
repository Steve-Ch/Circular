from django import forms
from products.models import Category

class ImportConfigurationForm(forms.Form):
    IMPORT_CHOICES = [
        ('all_except', 'Import All Products (with exclusions)'),
        ('specific', 'Import Only Specific Categories'),
    ]
    
    import_type = forms.ChoiceField(
        choices=IMPORT_CHOICES, 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='all_except'
    )
    
    # Use CheckboxSelectMultiple so we can loop through them as pills in the template
    excluded_categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(), 
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'category-pill-checkbox'})
    )

    included_categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(), 
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'category-pill-checkbox'})
    )
    
    import_with_price = forms.BooleanField(
        required=False,
        label="Import missing products with the Global Catalog Price (Automatically turns display ON)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    update_unpriced = forms.BooleanField(
        required=False,
        label="Update my existing unpriced inventory to match the Global Catalog Price (Turns display ON)",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    overwrite_all_prices = forms.BooleanField(
        required=False,
        label="Overwrite ALL my inventory prices to match the Global Catalog",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        self.merchant = kwargs.pop('merchant', None)
        super().__init__(*args, **kwargs)

        # Dynamic Default Exclusions from the Database Rule
        if self.merchant and self.merchant.category:
            if hasattr(self.merchant.category, 'exclusion_rule'):
                rule = self.merchant.category.exclusion_rule
                if rule.excluded_categories.exists():
                    self.fields['excluded_categories'].initial = rule.excluded_categories.all()

    def clean(self):
        cleaned_data = super().clean()
        import_type = cleaned_data.get('import_type')
        included_categories = cleaned_data.get('included_categories')

        if import_type == 'specific' and not included_categories:
            self.add_error('included_categories', 'You must select at least one category to include.')

        return cleaned_data
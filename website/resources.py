# resources.py
from import_export import resources, fields
from import_export.widgets import ManyToManyWidget
from products.models import Product, Category

class ProductResource(resources.ModelResource):
    # Map category names if included in the spreadsheet (comma-separated)
    categories = fields.Field(
        column_name='categories',
        attribute='categories',
        widget=ManyToManyWidget(Category, field='name', separator=',')
    )

    class Meta:
        model = Product
        # Use 'name' to identify unique existing records so duplicate product names are skipped
        import_id_fields = ('name',)
        fields = ('name', 'description', 'price', 'package', 'categories')
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """Sanitize name to title case before checking uniqueness."""
        if 'name' in row and row['name']:
            row['name'] = str(row['name']).strip().title()

    def init_instance(self, row, res_kwargs):
        """Ensure new instances imported via standard UI default to display=False."""
        instance = super().init_instance(row, res_kwargs)
        instance.display = False
        return instance
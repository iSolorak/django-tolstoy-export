# Django Tolstoy Export

A configurable Django app for exporting Tolstoy-compatible product CSV feeds.

It is designed to be installed in `INSTALLED_APPS` and configured from Django
settings. The package does not require Django Oscar, but it works well with
Oscar-style products, images, stockrecords, and request strategies.

## Installation

```bash
pip install django-tolstoy-export
```

```python
INSTALLED_APPS = [
    # ...
    "tolstoy_export",
]
```

Add the URLs if you want the package-provided export endpoint:

```python
from django.urls import include, path

urlpatterns = [
    path("feeds/", include("tolstoy_export.urls")),
]
```

The CSV will be available at `/feeds/tolstoy-csv/`.

## Settings

Configure the exported model, Tolstoy columns, queryset shaping, and languages:

```python
TOLSTOY_EXPORT = {
    "MODEL": "catalogue.Product",
    "FILENAME": "tolstoy_export_feed.csv",
    "LANGUAGES": ["en", "el"],
    "INCLUDE_LANGUAGE_IN_ID": True,
    "PUBLIC_FIELD": "is_public",
    "CURRENCY_CODE": "EUR",
    "CURRENCY_SYMBOL": "€",
    "FIELDS": {
        "id": "upc",
        "title": "title",
        "descriptionHtml": "db_field_description",
        "url": "get_absolute_url",
        "imageUrl": "images",
        "images": "images",
        "price": "price",
        "compareAtPrice": "compare_at_price",
        "inventory": "stockrecords.0.num_in_stock",
    },
    "QUERYSET_FILTERS": {
        "is_public": True,
    },
    "QUERYSET_EXCLUDES": {
        "stockrecords__num_in_stock": 0,
    },
    "SELECT_RELATED": ("parent",),
    "PREFETCH_RELATED": ("images", "stockrecords"),
    "ORDER_BY": ("id",),
}
```

Use `"LANGUAGES": "__all__"` to export every language in Django's `LANGUAGES`
setting. Use `None` or omit it to export only the currently active language.

## Field Mapping

`FIELDS` maps Tolstoy CSV column names to fields or attributes on your model.

Supported values:

- `"db_field_name"` for a direct model field;
- `"parent.description"` for dotted relation paths;
- `"stockrecords.0.num_in_stock"` for list/queryset indexes;
- `"get_absolute_url"` for a no-argument model method;
- `["upc", "id"]` for fallback fields;
- a callable, or an import path to a callable.

The Tolstoy columns are:

```text
id,title,descriptionHtml,url,imageUrl,images,price,compareAtPrice,currencyCode,currencySymbol,inventory
```

`imageUrl` is the first image. `images` is exported as a comma-separated list
of additional image URLs. A mapped value can be a URL string, image object with
`original.url`, list, tuple, queryset, or related manager.

## Custom View

You can also call the response helper directly:

```python
from tolstoy_export.django import tolstoy_csv_response


def export_tolstoy_csv(request):
    return tolstoy_csv_response(request)
```

Per-view overrides are useful when you want two exports from the same settings:

```python
def export_single_language_tolstoy_csv(request):
    return tolstoy_csv_response(
        request,
        include_all_languages=False,
        include_language_in_id=False,
        require_public=False,
    )
```

## Generic CSV Writer

For non-view usage:

```python
from io import StringIO
from tolstoy_export import write_products_csv

output = StringIO()
write_products_csv(
    output,
    products,
    request=request,
    languages=["en", "el"],
    include_language_in_id=True,
    fields={
        "id": "sku",
        "title": "name",
        "descriptionHtml": "description",
        "url": "get_absolute_url",
    },
)
csv_text = output.getvalue()
```

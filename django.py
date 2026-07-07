from django.conf import settings
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse

from .conf import tolstoy_export_settings
from .exporter import write_products_csv


def get_model_from_label(model_label):
    if not model_label:
        try:
            from oscar.core.loading import get_model
        except ImportError:
            raise ImproperlyConfigured("Set TOLSTOY_EXPORT['MODEL'] to '<app_label>.<ModelName>'.")

        return get_model("catalogue", "Product")

    if "." not in model_label:
        raise ImproperlyConfigured("TOLSTOY_EXPORT['MODEL'] must look like '<app_label>.<ModelName>'.")

    app_label, model_name = model_label.split(".", 1)
    return apps.get_model(app_label, model_name)


def get_tolstoy_products_queryset(config):
    Product = get_model_from_label(config.get("MODEL"))

    products = Product.objects.all()

    filters = config.get("QUERYSET_FILTERS") or {}
    if filters:
        products = products.filter(**filters)

    excludes = config.get("QUERYSET_EXCLUDES") or {}
    if excludes:
        products = products.exclude(**excludes)

    select_related = config.get("SELECT_RELATED") or ()
    if select_related:
        products = products.select_related(*select_related)

    prefetch_related = config.get("PREFETCH_RELATED") or ()
    if prefetch_related:
        products = products.prefetch_related(*prefetch_related)

    order_by = config.get("ORDER_BY") or ()
    if order_by:
        products = products.order_by(*order_by)

    return products


def oscar_default_overrides(require_public=True):
    excludes = {
        "structure": "parent",
        "stockrecords__num_in_stock": 0,
        "stockrecords__price_excl_tax": 0,
        "stockrecords__price_retail": 0,
        "stockrecords__cost_price": 0,
    }
    if require_public:
        excludes["is_public"] = False

    return {
        "SELECT_RELATED": ("parent", "product_class"),
        "PREFETCH_RELATED": ("images", "parent__images", "stockrecords"),
        "QUERYSET_EXCLUDES": excludes,
        "FIELDS": {
            "id": ["upc", "id"],
            "title": ["get_title", "title"],
            "descriptionHtml": ["parent.description", "description"],
            "url": "get_absolute_url",
            "imageUrl": ["images", "parent.images"],
            "images": ["images", "parent.images"],
            "inventory": "stockrecords.0.num_in_stock",
        },
    }


def tolstoy_csv_response(
    request,
    products=None,
    filename=None,
    include_all_languages=None,
    include_language_in_id=None,
    require_public=True,
    currency_code=None,
    currency_symbol=None,
):
    overrides = {}
    if include_all_languages is True:
        overrides["LANGUAGES"] = [language_code for language_code, language_name in settings.LANGUAGES]
    elif include_all_languages is False:
        overrides["LANGUAGES"] = None
    if include_language_in_id is not None:
        overrides["INCLUDE_LANGUAGE_IN_ID"] = include_language_in_id
    if filename:
        overrides["FILENAME"] = filename
    if currency_code:
        overrides["CURRENCY_CODE"] = currency_code
    if currency_symbol:
        overrides["CURRENCY_SYMBOL"] = currency_symbol

    user_config = getattr(settings, "TOLSTOY_EXPORT", None)
    if not user_config:
        overrides.update(oscar_default_overrides(require_public=require_public))

    config = tolstoy_export_settings(overrides=overrides)
    public_field = config.get("PUBLIC_FIELD")
    if user_config and require_public and public_field:
        excludes = dict(config.get("QUERYSET_EXCLUDES") or {})
        excludes.setdefault(public_field, False)
        config["QUERYSET_EXCLUDES"] = excludes

    if products is None:
        products = get_tolstoy_products_queryset(config)

    languages = config.get("LANGUAGES")
    if languages == "__all__":
        languages = [language_code for language_code, language_name in settings.LANGUAGES]

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="%s"' % config["FILENAME"]

    write_products_csv(
        response,
        products,
        request=request,
        languages=languages,
        include_language_in_id=config["INCLUDE_LANGUAGE_IN_ID"],
        currency_code=config["CURRENCY_CODE"],
        currency_symbol=config["CURRENCY_SYMBOL"],
        fields=config["FIELDS"],
    )

    return response

from django.conf import settings


DEFAULT_TOLSTOY_EXPORT = {
    "MODEL": None,
    "FILENAME": "tolstoy_export_feed.csv",
    "FIELDS": {
        "id": ["upc", "id"],
        "title": ["get_title", "title"],
        "descriptionHtml": ["parent.description", "description"],
        "url": "get_absolute_url",
        "imageUrl": ["images", "parent.images"],
        "images": ["images", "parent.images"],
        "price": None,
        "compareAtPrice": None,
        "currencyCode": None,
        "currencySymbol": None,
        "inventory": None,
    },
    "LANGUAGES": None,
    "INCLUDE_LANGUAGE_IN_ID": False,
    "PUBLIC_FIELD": None,
    "CURRENCY_CODE": "EUR",
    "CURRENCY_SYMBOL": "€",
    "QUERYSET_FILTERS": {},
    "QUERYSET_EXCLUDES": {},
    "SELECT_RELATED": (),
    "PREFETCH_RELATED": (),
    "ORDER_BY": (),
}


def tolstoy_export_settings(overrides=None):
    config = DEFAULT_TOLSTOY_EXPORT.copy()
    user_config = getattr(settings, "TOLSTOY_EXPORT", {})
    config.update(user_config)

    fields = DEFAULT_TOLSTOY_EXPORT["FIELDS"].copy()
    fields.update(user_config.get("FIELDS", {}))
    if overrides and overrides.get("FIELDS"):
        fields.update(overrides["FIELDS"])

    if overrides:
        config.update({key: value for key, value in overrides.items() if key != "FIELDS"})

    config["FIELDS"] = fields
    return config

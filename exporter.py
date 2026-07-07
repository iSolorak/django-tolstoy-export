import csv
import html
import re
import unicodedata
from decimal import Decimal
from html.parser import HTMLParser
from io import StringIO
from urllib.parse import urlparse

try:
    from django.utils.encoding import force_str
except ImportError:
    force_str = str

try:
    from django.utils.module_loading import import_string
    from django.utils import translation
    from django.core.exceptions import ImproperlyConfigured
except ImportError:
    import_string = None
    translation = None
    ImproperlyConfigured = RuntimeError


HEADERS = [
    "id",
    "title",
    "descriptionHtml",
    "url",
    "imageUrl",
    "images",
    "price",
    "compareAtPrice",
    "currencyCode",
    "currencySymbol",
    "inventory",
]


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        return self.text.getvalue()


def strip_html_tags(value):
    stripper = MLStripper()
    stripper.feed(force_str(value))
    return stripper.get_data()


def clean_csv_text(value):
    if not value:
        return ""

    value = force_str(value)
    value = html.unescape(value)
    value = strip_html_tags(value)
    value = unicodedata.normalize("NFKC", value)

    replacements = {
        "\xa0": " ",
        "\r": " ",
        "\n": " ",
        "\t": " ",
        "’": "'",
        "‘": "'",
        "“": "",
        "”": "",
        '"': "",
        ";": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return re.sub(r"\s+", " ", value).strip()


def clean_description(value):
    if not value:
        return ""

    value = force_str(value)
    value = html.unescape(value)
    value = strip_html_tags(value)
    value = unicodedata.normalize("NFKC", value)

    replacements = {
        "\xa0": " ",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = re.sub(r"[\r\n\t]+", " ", value)
    value = value.replace(",", " ").replace('"', "'")

    return re.sub(r"\s+", " ", value).strip()


def absolute_uri(request, url):
    if not url:
        return ""

    url = force_str(url)
    if urlparse(url).scheme in ("http", "https"):
        return url

    if request is None:
        return url

    try:
        return request.build_absolute_uri(url)
    except Exception:
        return url


def product_absolute_url(product, request=None):
    try:
        return product.get_absolute_url(request=request)
    except TypeError:
        return product.get_absolute_url()


def is_related_manager(value):
    return hasattr(value, "all") and callable(value.all)


def list_from_value(value):
    if value in ("", None):
        return []

    if is_related_manager(value):
        return list(value.all())

    if isinstance(value, (list, tuple)):
        return list(value)

    return [value]


def call_value(value, request=None):
    if not callable(value):
        return value

    try:
        return value(request=request)
    except TypeError:
        return value()


def resolve_path(obj, path, request=None):
    if path in ("", None):
        return ""

    value = obj
    for part in force_str(path).split("."):
        value = call_value(value, request=request)

        if value in ("", None):
            return ""

        if part.isdigit():
            values = list_from_value(value)
            index = int(part)
            value = values[index] if len(values) > index else ""
            continue

        value = getattr(value, part, "")

    return call_value(value, request=request)


def resolve_import_string(path):
    if import_string is None:
        return None

    try:
        return import_string(path)
    except Exception:
        return None


def resolve_field(product, field_spec, request=None, language_code=None, default=""):
    if callable(field_spec):
        return field_spec(product)

    if isinstance(field_spec, dict):
        source = field_spec.get("source")
        default = field_spec.get("default", default)
        value = resolve_field(product, source, request=request, language_code=language_code, default=default)

        transform = field_spec.get("transform")
        if transform:
            if isinstance(transform, str):
                transform = resolve_import_string(transform)
            if callable(transform):
                return transform(value, product=product, request=request, language_code=language_code)

        return value

    if isinstance(field_spec, (list, tuple)):
        for item in field_spec:
            value = resolve_field(product, item, request=request, language_code=language_code, default="")
            if value not in ("", None, []):
                return value
        return default

    if isinstance(field_spec, str):
        imported = resolve_import_string(field_spec)
        if callable(imported):
            return imported(product)

        return resolve_path(product, field_spec, request=request)

    return default


def product_title(product):
    if hasattr(product, "get_title"):
        return product.get_title()

    return getattr(product, "title", "")


def product_description(product):
    if getattr(product, "is_standalone", False):
        return getattr(product, "description", "")

    parent = getattr(product, "parent", None)
    if parent is not None:
        return getattr(parent, "description", "") or getattr(product, "description", "")

    return getattr(product, "description", "")


def product_images(product):
    try:
        images = list(product.images.all())
    except Exception:
        images = []

    parent = getattr(product, "parent", None)
    if not images and parent is not None:
        try:
            images = list(parent.images.all())
        except Exception:
            images = []

    return images


def image_url(request, image):
    if isinstance(image, str):
        return absolute_uri(request, image)

    original = getattr(image, "original", None)
    if not original:
        return ""

    return absolute_uri(request, original.url)


def image_urls_from_value(request, value):
    urls = []
    for image in list_from_value(value):
        url = image_url(request, image)
        if url:
            urls.append(url)
    return urls


def first_stockrecord(product):
    try:
        return product.stockrecords.first()
    except Exception:
        return None


def stockrecord_price(stockrecord):
    if stockrecord is None:
        return ""

    price_retail = getattr(stockrecord, "price_retail", None)
    if price_retail:
        return price_retail

    return getattr(stockrecord, "price_excl_tax", "") or ""


def strategy_price_values(request, product, stockrecord):
    price = ""
    compare_at_price = ""

    strategy = getattr(request, "strategy", None)
    if strategy is not None:
        try:
            strategy_product = strategy.fetch_for_product(product)
            price_obj = strategy_product.price
            discount = getattr(price_obj, "discount", 0) or 0
            price = price_obj.incl_tax - price_obj.incl_tax * (discount / Decimal("100"))
        except Exception:
            price = ""

        try:
            compare_at_price = strategy.fetch_for_product(product).price.incl_tax
        except Exception:
            compare_at_price = ""

    if not compare_at_price:
        compare_at_price = stockrecord_price(stockrecord)

    if price == "":
        price = compare_at_price

    return price, compare_at_price


def build_product_row(
    product,
    request=None,
    language_code=None,
    currency_code="EUR",
    currency_symbol="€",
    include_language_in_id=False,
    fields=None,
):
    stockrecord = first_stockrecord(product)
    fields = fields or {}
    product_id = resolve_field(product, fields.get("id"), request=request, language_code=language_code)
    if product_id in ("", None):
        product_id = getattr(product, "upc", None) or getattr(product, "id", "")

    if include_language_in_id and language_code:
        product_id = "%s-%s" % (product_id, language_code)

    image_value = resolve_field(
        product,
        fields.get("imageUrl") or fields.get("images"),
        request=request,
        language_code=language_code,
    )
    images_value = resolve_field(
        product,
        fields.get("images") or fields.get("imageUrl"),
        request=request,
        language_code=language_code,
    )
    image_urls = image_urls_from_value(request, image_value)
    extra_image_urls = image_urls_from_value(request, images_value)
    if not image_urls:
        fallback_images = product_images(product)
        image_urls = image_urls_from_value(request, fallback_images)
        extra_image_urls = image_urls

    price = resolve_field(product, fields.get("price"), request=request, language_code=language_code)
    compare_at_price = resolve_field(
        product,
        fields.get("compareAtPrice"),
        request=request,
        language_code=language_code,
    )
    if price in ("", None) and compare_at_price in ("", None):
        price, compare_at_price = strategy_price_values(request, product, stockrecord)
    elif price in ("", None):
        price = compare_at_price
    elif compare_at_price in ("", None):
        compare_at_price = stockrecord_price(stockrecord)

    title = resolve_field(product, fields.get("title"), request=request, language_code=language_code)
    if title in ("", None):
        title = product_title(product)

    description = resolve_field(product, fields.get("descriptionHtml"), request=request, language_code=language_code)
    if description in ("", None):
        description = product_description(product)

    product_url = resolve_field(product, fields.get("url"), request=request, language_code=language_code)
    if product_url in ("", None):
        product_url = product_absolute_url(product, request=request)

    inventory = resolve_field(product, fields.get("inventory"), request=request, language_code=language_code)
    if inventory in ("", None):
        inventory = getattr(stockrecord, "num_in_stock", 0) if stockrecord else 0

    return [
        product_id,
        clean_csv_text(title),
        clean_csv_text(clean_description(description)),
        absolute_uri(request, product_url),
        image_urls[0] if image_urls else "",
        ",".join(extra_image_urls[1:]) if len(extra_image_urls) > 1 else "",
        price,
        compare_at_price,
        currency_code,
        currency_symbol,
        inventory,
    ]


def get_current_language():
    if translation is None:
        return None

    try:
        return translation.get_language()
    except ImproperlyConfigured:
        return None


def activate_language(language_code):
    if translation is None or not language_code:
        return

    try:
        translation.activate(language_code)
    except ImproperlyConfigured:
        return


def write_products_csv(
    output,
    products,
    request=None,
    languages=None,
    include_language_in_id=False,
    currency_code="EUR",
    currency_symbol="€",
    fields=None,
):
    writer = csv.writer(
        output,
        delimiter=",",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writerow(HEADERS)

    languages = languages or [None]
    previous_language = get_current_language()

    try:
        for language_code in languages:
            activate_language(language_code)

            for product in products:
                writer.writerow(
                    build_product_row(
                        product,
                        request=request,
                        language_code=language_code,
                        currency_code=currency_code,
                        currency_symbol=currency_symbol,
                        include_language_in_id=include_language_in_id,
                        fields=fields,
                    )
                )
    finally:
        activate_language(previous_language)

    return output

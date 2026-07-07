from .django import tolstoy_csv_response


def export_csv(request):
    return tolstoy_csv_response(request)

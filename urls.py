from django.urls import path

from .views import export_csv


app_name = "tolstoy_export"

urlpatterns = [
    path("tolstoy-csv/", export_csv, name="csv"),
]

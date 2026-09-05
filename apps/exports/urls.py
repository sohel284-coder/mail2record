from django.urls import path

from . import views

app_name = "exports"

urlpatterns = [
    path("records.csv", views.export_csv, name="records_csv"),
    path("records.xlsx", views.export_xlsx, name="records_xlsx"),
]

from django.urls import path

from . import views

app_name = "records_ui"

urlpatterns = [
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:pk>/", views.review_detail, name="review_detail"),
    path("records/", views.record_list, name="list"),
    path("records/<int:pk>/", views.record_detail, name="detail"),
]

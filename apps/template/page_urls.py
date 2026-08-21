from django.urls import path

from . import views

app_name = "templates_ui"

urlpatterns = [
    path("", views.template_list, name="list"),
    path("new/", views.template_create, name="create"),
    path("<int:pk>/edit/", views.template_edit, name="edit"),
]

from rest_framework.routers import DefaultRouter
from .api_views import EmailViewSet

router = DefaultRouter()
router.register("emails", EmailViewSet, basename="email")

app_name = "emails_api"
urlpatterns = router.urls


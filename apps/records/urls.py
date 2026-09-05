from rest_framework.routers import DefaultRouter

from .api_views import RecordViewSet

router = DefaultRouter()
router.register("records", RecordViewSet, basename="record")

app_name = "records_api"
urlpatterns = router.urls

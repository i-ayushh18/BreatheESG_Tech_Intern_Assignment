from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    NormalizedRecordViewSet, ClientViewSet, DataIngestionView,
    DataIngestionViewSet, RawRecordViewSet
)

router = DefaultRouter()
router.register(r'records', NormalizedRecordViewSet, basename='normalizedrecord')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'ingestions', DataIngestionViewSet, basename='dataingestion')
router.register(r'raw-records', RawRecordViewSet, basename='rawrecord')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/ingest/', DataIngestionView.as_view(), name='data-ingestion'),
]

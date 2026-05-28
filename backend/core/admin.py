from django.contrib import admin
from .models import (
	Client, DataIngestion, RawRecord, NormalizedRecord,
	UnitConversion, EmissionFactor, AuditLog, DataQualityFlag
)

admin.site.register(Client)
admin.site.register(DataIngestion)
admin.site.register(RawRecord)
admin.site.register(NormalizedRecord)
admin.site.register(UnitConversion)
admin.site.register(EmissionFactor)
admin.site.register(AuditLog)
admin.site.register(DataQualityFlag)

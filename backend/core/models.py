from django.db import models
from django.contrib.auth import get_user_model

# Multi-tenancy: Each client/company has its own data scope
class Client(models.Model):
	name = models.CharField(max_length=255)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name

# Data ingestion jobs (tracks uploads and status)
class DataIngestion(models.Model):
	SOURCE_CHOICES = [
		('sap', 'SAP'),
		('utility', 'Utility'),
		('travel', 'Travel'),
	]
	STATUS_CHOICES = [
		('processing', 'Processing'),
		('completed', 'Completed'),
		('failed', 'Failed'),
	]
	client = models.ForeignKey(Client, on_delete=models.CASCADE)
	source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
	filename = models.CharField(max_length=255)
	uploaded_at = models.DateTimeField(auto_now_add=True)
	uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
	error_log = models.TextField(blank=True, null=True)

	def __str__(self):
		return f'{self.source_type}: {self.filename}'

# Immutable raw data storage for traceability
class RawRecord(models.Model):
	ingestion = models.ForeignKey(DataIngestion, on_delete=models.CASCADE)
	row_number = models.IntegerField()
	raw_data = models.JSONField()
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f'{self.ingestion.filename} row {self.row_number}'

# Normalized, computed data for analytics and workflow
class NormalizedRecord(models.Model):
	SCOPE_CHOICES = [
		(1, 'Scope 1'),
		(2, 'Scope 2'),
		(3, 'Scope 3'),
	]
	STATUS_CHOICES = [
		('pending', 'Pending'),
		('flagged', 'Flagged'),
		('approved', 'Approved'),
		('locked', 'Locked'),
	]
	raw_record = models.ForeignKey(RawRecord, on_delete=models.CASCADE)
	client = models.ForeignKey(Client, on_delete=models.CASCADE)
	scope = models.IntegerField(choices=SCOPE_CHOICES)
	activity_type = models.CharField(max_length=32)
	activity_value = models.FloatField()
	activity_unit = models.CharField(max_length=16)
	emission_factor = models.FloatField()
	emission_factor_source = models.CharField(max_length=64)
	co2e_kg = models.FloatField()
	facility = models.CharField(max_length=128, blank=True, null=True)
	location = models.CharField(max_length=128, blank=True, null=True)
	reporting_period = models.CharField(max_length=64, blank=True, null=True)
	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
	flagged_reason = models.TextField(blank=True, null=True)
	approved_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_records')
	approved_at = models.DateTimeField(blank=True, null=True)
	is_edited = models.BooleanField(default=False)
	# Reason for manual edits performed by an analyst before locking
	edit_reason = models.TextField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f'{self.activity_type} {self.co2e_kg:.2f} kg CO2e'

# Lookup table for unit conversions
class UnitConversion(models.Model):
	from_unit = models.CharField(max_length=16)
	to_unit = models.CharField(max_length=16)
	conversion_factor = models.FloatField()
	source_type = models.CharField(max_length=20)

	def __str__(self):
		return f'{self.from_unit} -> {self.to_unit} ({self.source_type})'

# Reference data for emission factors
class EmissionFactor(models.Model):
	activity_type = models.CharField(max_length=32)
	fuel_type = models.CharField(max_length=32, blank=True, null=True)
	grid_region = models.CharField(max_length=32, blank=True, null=True)
	transport_mode = models.CharField(max_length=32, blank=True, null=True)
	factor_value = models.FloatField()
	unit = models.CharField(max_length=16)
	source = models.CharField(max_length=64)
	valid_from = models.IntegerField()
	valid_to = models.IntegerField()

	def __str__(self):
		qualifier = self.fuel_type or self.grid_region or self.transport_mode or self.activity_type
		return f'{self.activity_type}: {qualifier} = {self.factor_value}'

# Audit log for all edits (compliance)
class AuditLog(models.Model):
	record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE)
	changed_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
	changed_at = models.DateTimeField(auto_now_add=True)
	field_name = models.CharField(max_length=64)
	old_value = models.TextField()
	new_value = models.TextField()
	reason = models.TextField(blank=True, null=True)

	def __str__(self):
		return f'{self.field_name}: {self.old_value} -> {self.new_value}'

# Automatic data quality flags
class DataQualityFlag(models.Model):
	FLAG_TYPE_CHOICES = [
		('outlier', 'Outlier'),
		('unit_mismatch', 'Unit Mismatch'),
		('gap', 'Gap'),
		('duplicate', 'Duplicate'),
	]
	SEVERITY_CHOICES = [
		('warning', 'Warning'),
		('error', 'Error'),
	]
	record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE)
	flag_type = models.CharField(max_length=32, choices=FLAG_TYPE_CHOICES)
	severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES)
	description = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f'{self.severity}: {self.description}'

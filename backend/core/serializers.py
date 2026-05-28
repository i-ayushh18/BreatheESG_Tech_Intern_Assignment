from rest_framework import serializers
from .models import (
    Client, DataIngestion, RawRecord, NormalizedRecord,
    UnitConversion, EmissionFactor, AuditLog, DataQualityFlag
)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


class DataIngestionSerializer(serializers.ModelSerializer):
    raw_record_count = serializers.SerializerMethodField()
    normalized_record_count = serializers.SerializerMethodField()
    failed_row_count = serializers.SerializerMethodField()

    class Meta:
        model = DataIngestion
        fields = [
            'id', 'client', 'source_type', 'filename', 'uploaded_at',
            'uploaded_by', 'status', 'error_log', 'raw_record_count',
            'normalized_record_count', 'failed_row_count'
        ]
        read_only_fields = ['id', 'uploaded_at', 'status']

    def get_raw_record_count(self, obj):
        return obj.rawrecord_set.count()

    def get_normalized_record_count(self, obj):
        return NormalizedRecord.objects.filter(raw_record__ingestion=obj).count()

    def get_failed_row_count(self, obj):
        return RawRecord.objects.filter(
            ingestion=obj,
            normalizedrecord__isnull=True
        ).count()


class RawRecordSerializer(serializers.ModelSerializer):
    ingestion_source_type = serializers.CharField(source='ingestion.source_type', read_only=True)
    ingestion_filename = serializers.CharField(source='ingestion.filename', read_only=True)
    ingestion_status = serializers.CharField(source='ingestion.status', read_only=True)
    normalized_count = serializers.SerializerMethodField()
    validation_error = serializers.SerializerMethodField()

    class Meta:
        model = RawRecord
        fields = [
            'id', 'ingestion', 'ingestion_source_type', 'ingestion_filename',
            'ingestion_status', 'row_number', 'raw_data', 'normalized_count',
            'validation_error', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_normalized_count(self, obj):
        return obj.normalizedrecord_set.count()

    def get_validation_error(self, obj):
        if obj.normalizedrecord_set.exists():
            return ''

        source_type = obj.ingestion.source_type
        raw_data = obj.raw_data
        if source_type == 'sap':
            return 'Invalid or missing quantity' if not _is_number(raw_data.get('quantity')) else 'No normalized record created'
        if source_type == 'utility':
            return 'Invalid or missing consumption' if not _is_number(raw_data.get('consumption')) else 'No normalized record created'
        if source_type == 'travel':
            if not raw_data.get('segments'):
                return 'No travel segments found'
            return 'No supported travel segments created a normalized record'
        return 'No normalized record created'


class NormalizedRecordSerializer(serializers.ModelSerializer):
    quality_flags = serializers.SerializerMethodField()
    flag_count = serializers.SerializerMethodField()
    highest_severity = serializers.SerializerMethodField()

    class Meta:
        model = NormalizedRecord
        fields = [
            'id', 'raw_record', 'client', 'scope', 'activity_type',
            'activity_value', 'activity_unit', 'emission_factor',
            'emission_factor_source', 'co2e_kg', 'facility', 'location',
            'reporting_period', 'status', 'flagged_reason', 'approved_by',
            'approved_at', 'is_edited', 'created_at', 'quality_flags',
            'flag_count', 'highest_severity'
        ]
        read_only_fields = ['id', 'created_at', 'approved_at']

    def get_quality_flags(self, obj):
        flags = obj.dataqualityflag_set.order_by('-severity', '-created_at')
        return DataQualityFlagSerializer(flags, many=True).data

    def get_flag_count(self, obj):
        return obj.dataqualityflag_set.count()

    def get_highest_severity(self, obj):
        if obj.dataqualityflag_set.filter(severity='error').exists():
            return 'error'
        if obj.dataqualityflag_set.filter(severity='warning').exists():
            return 'warning'
        return ''


class UnitConversionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitConversion
        fields = ['id', 'from_unit', 'to_unit', 'conversion_factor', 'source_type']
        read_only_fields = ['id']


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = [
            'id', 'activity_type', 'fuel_type', 'grid_region',
            'transport_mode', 'factor_value', 'unit', 'source',
            'valid_from', 'valid_to'
        ]
        read_only_fields = ['id']


class AuditLogSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'record', 'changed_by', 'changed_by_username',
            'changed_at', 'field_name', 'old_value', 'new_value', 'reason'
        ]
        read_only_fields = ['id', 'changed_at']


class DataQualityFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataQualityFlag
        fields = ['id', 'record', 'flag_type', 'severity', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class NormalizedRecordDetailSerializer(NormalizedRecordSerializer):
    raw_data = serializers.SerializerMethodField()
    
    class Meta(NormalizedRecordSerializer.Meta):
        fields = NormalizedRecordSerializer.Meta.fields + ['raw_data']
    
    def get_raw_data(self, obj):
        return obj.raw_record.raw_data


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False

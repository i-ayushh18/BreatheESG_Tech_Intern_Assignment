"""Data quality checks for flagging suspicious data"""
from datetime import timedelta
from django.db.models import Avg
from .models import NormalizedRecord, DataQualityFlag


class DataQualityChecker:
    """Automatic data quality checks"""
    
    @staticmethod
    def check_outlier(record):
        """Check if value is 3x rolling average"""
        recent = NormalizedRecord.objects.filter(
            client=record.client,
            facility=record.facility,
            activity_type=record.activity_type,
            created_at__gte=record.created_at - timedelta(days=90)
        ).exclude(id=record.id)

        if not recent.exists():
            return

        avg = recent.aggregate(Avg('activity_value'))['activity_value__avg']
        if avg and record.activity_value > avg * 3:
            DataQualityFlag.objects.create(
                record=record,
                flag_type='outlier',
                severity='warning',
                description=f'Value {record.activity_value} is 3x the rolling average {avg:.2f}'
            )
    
    @staticmethod
    def check_unit_consistency(record):
        """Check if unit changed for same facility"""
        previous = NormalizedRecord.objects.filter(
            client=record.client,
            facility=record.facility,
            activity_type=record.activity_type
        ).exclude(id=record.id).order_by('-created_at').first()

        if previous and previous.activity_unit != record.activity_unit:
            DataQualityFlag.objects.create(
                record=record,
                flag_type='unit_mismatch',
                severity='warning',
                description=f'Unit changed from {previous.activity_unit} to {record.activity_unit}'
            )
    
    @staticmethod
    def check_impossible_values(record):
        """Check for impossible values"""
        if record.activity_type == 'flight' and record.activity_value < 100:
            DataQualityFlag.objects.create(
                record=record,
                flag_type='outlier',
                severity='error',
                description='Flight distance under 100km is suspicious'
            )
        
        if record.activity_value < 0:
            DataQualityFlag.objects.create(
                record=record,
                flag_type='outlier',
                severity='error',
                description='Negative consumption value'
            )
    
    @staticmethod
    def run_all_checks(record):
        """Run all data quality checks"""
        DataQualityChecker.check_outlier(record)
        DataQualityChecker.check_unit_consistency(record)
        DataQualityChecker.check_impossible_values(record)

        flags = record.dataqualityflag_set.order_by('-created_at')
        if record.status == 'pending' and flags.exists():
            primary_flag = flags.filter(severity='error').first() or flags.first()
            record.status = 'flagged'
            record.flagged_reason = primary_flag.description
            record.save(update_fields=['status', 'flagged_reason'])

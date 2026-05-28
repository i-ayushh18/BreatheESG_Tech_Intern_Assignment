import csv
import json
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from .models import (
    Client, DataIngestion, RawRecord, NormalizedRecord,
    AuditLog
)
from .serializers import (
    ClientSerializer, DataIngestionSerializer,
    NormalizedRecordSerializer, NormalizedRecordDetailSerializer,
    AuditLogSerializer, RawRecordSerializer
)
from .parsers import SAPParser, UtilityParser, TravelParser
from .normalizers import Normalizer
from .quality_checks import DataQualityChecker


class DataIngestionView(APIView):
    """Handle file upload and data ingestion"""
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request):
        source_type = request.data.get('source_type')
        file = request.data.get('file')
        client_id = request.data.get('client_id', 1)
        
        if not source_type or not file:
            return Response(
                {'error': 'source_type and file are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create ingestion job
        ingestion = DataIngestion.objects.create(
            client=client,
            source_type=source_type,
            filename=file.name,
            uploaded_by=request.user if request.user.is_authenticated else None,
            status='processing'
        )
        
        try:
            # Parse file based on source type
            if source_type == 'sap':
                self._process_sap(file, ingestion, client)
            elif source_type == 'utility':
                self._process_utility(file, ingestion, client)
            elif source_type == 'travel':
                self._process_travel(file, ingestion, client)
            else:
                raise ValueError(f'Unknown source type: {source_type}')
            
            ingestion.status = 'completed'
            ingestion.save()
            
            return Response(
                DataIngestionSerializer(ingestion).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            ingestion.status = 'failed'
            ingestion.error_log = str(e)
            ingestion.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _process_sap(self, file, ingestion, client):
        """Process SAP S/4HANA Material Document OData JSON, with CSV fallback."""
        decoded_file = file.read().decode('utf-8')
        if decoded_file.lstrip().startswith('{'):
            parsed_rows = SAPParser.parse_odata_payload(json.loads(decoded_file))
        else:
            reader = csv.DictReader(decoded_file.splitlines())
            parsed_rows = [SAPParser.parse_row(row) for row in reader]

        self._store_and_normalize_rows(parsed_rows, ingestion, client, SAPParser.validate, Normalizer.normalize_sap)

    def _store_and_normalize_rows(self, parsed_rows, ingestion, client, validator, normalizer):
        for row_number, parsed_data in enumerate(parsed_rows, start=1):
            raw_record = RawRecord.objects.create(
                ingestion=ingestion,
                row_number=row_number,
                raw_data=parsed_data
            )

            if validator(parsed_data):
                normalized = normalizer(raw_record, client)
                DataQualityChecker.run_all_checks(normalized)

    def _process_utility(self, file, ingestion, client):
        """Process utility CSV file"""
        decoded_file = file.read().decode('utf-8')
        reader = csv.DictReader(decoded_file.splitlines())
        parsed_rows = [UtilityParser.parse_row(row) for row in reader]
        self._store_and_normalize_rows(parsed_rows, ingestion, client, UtilityParser.validate, Normalizer.normalize_utility)
    
    def _process_travel(self, file, ingestion, client):
        """Process SAP Concur Itinerary v4 JSON, with simplified JSON fallback."""
        data = json.loads(file.read().decode('utf-8'))

        if isinstance(data, dict) and 'itineraries' in data:
            trips = [
                TravelParser.parse_concur_itinerary(itinerary)
                for itinerary in data.get('itineraries', [])
            ]
        elif isinstance(data, dict) and 'Bookings' in data:
            trips = [TravelParser.parse_concur_itinerary(data)]
        elif isinstance(data, list):
            trips = [TravelParser.parse_trip(trip) for trip in data]
        else:
            trips = [TravelParser.parse_trip(data)]

        for row_number, parsed_data in enumerate(trips, start=1):
            
            raw_record = RawRecord.objects.create(
                ingestion=ingestion,
                row_number=row_number,
                raw_data=parsed_data
            )
            
            normalized_records = Normalizer.normalize_travel(raw_record, client)
            for normalized in normalized_records:
                DataQualityChecker.run_all_checks(normalized)


class NormalizedRecordViewSet(viewsets.ModelViewSet):
    """ViewSet for NormalizedRecord with filtering"""
    queryset = NormalizedRecord.objects.select_related('client', 'raw_record').all()
    serializer_class = NormalizedRecordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['facility', 'activity_type', 'status']
    ordering_fields = ['created_at', 'co2e_kg', 'activity_value']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return NormalizedRecordDetailSerializer
        return NormalizedRecordSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by client
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        # Filter by scope
        scope = self.request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by activity type
        activity_type = self.request.query_params.get('activity_type')
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a record"""
        record = self.get_object()
        
        if record.status == 'locked':
            return Response(
                {'error': 'Cannot approve locked records'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create audit log
        AuditLog.objects.create(
            record=record,
            changed_by=request.user if request.user.is_authenticated else None,
            field_name='status',
            old_value=record.status,
            new_value='approved',
            reason='Approved by analyst'
        )
        
        record.status = 'approved'
        record.approved_by = request.user if request.user.is_authenticated else None
        record.approved_at = timezone.now()
        record.save()
        
        return Response(NormalizedRecordSerializer(record).data)
    
    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        """Flag a record"""
        record = self.get_object()
        reason = request.data.get('reason', '')
        
        if record.status == 'locked':
            return Response(
                {'error': 'Cannot flag locked records'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create audit log
        AuditLog.objects.create(
            record=record,
            changed_by=request.user if request.user.is_authenticated else None,
            field_name='status',
            old_value=record.status,
            new_value='flagged',
            reason=reason
        )
        
        record.status = 'flagged'
        record.flagged_reason = reason
        record.save()
        
        return Response(NormalizedRecordSerializer(record).data)
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Lock a record (no further edits)"""
        record = self.get_object()
        
        if record.status != 'approved':
            return Response(
                {'error': 'Can only lock approved records'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create audit log before state transition
        AuditLog.objects.create(
            record=record,
            changed_by=request.user if request.user.is_authenticated else None,
            field_name='status',
            old_value=record.status,
            new_value='locked',
            reason='Locked for audit'
        )

        record.status = 'locked'
        record.save()
        
        return Response(NormalizedRecordSerializer(record).data)
    
    @action(detail=True, methods=['get'])
    def audit_log(self, request, pk=None):
        """Get audit log for a record"""
        record = self.get_object()
        audit_logs = AuditLog.objects.filter(record=record).order_by('-changed_at')
        
        return Response(AuditLogSerializer(audit_logs, many=True).data)
    
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """Approve multiple records"""
        record_ids = request.data.get('record_ids', [])
        
        if not record_ids:
            return Response(
                {'error': 'record_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        records = NormalizedRecord.objects.filter(
            id__in=record_ids,
            status__in=['pending', 'flagged']
        )

        # Prepare bulk AuditLog entries to avoid N+1 queries
        audit_logs = []
        now = timezone.now()
        approver_id = request.user.id if request.user.is_authenticated else None
        record_ids_to_update = []

        for record in records:
            audit_logs.append(AuditLog(
                record=record,
                changed_by=request.user if request.user.is_authenticated else None,
                field_name='status',
                old_value=record.status,
                new_value='approved',
                reason='Bulk approved'
            ))
            record_ids_to_update.append(record.id)

        if audit_logs:
            AuditLog.objects.bulk_create(audit_logs)

        # Bulk update records (use _id field for approved_by)
        update_kwargs = {
            'status': 'approved',
            'approved_at': now,
        }
        if approver_id:
            update_kwargs['approved_by_id'] = approver_id

        NormalizedRecord.objects.filter(id__in=record_ids_to_update).update(**update_kwargs)

        return Response({'message': f'Approved {len(record_ids_to_update)} records'})

    @action(detail=True, methods=['patch'])
    def edit(self, request, pk=None):
        """Allow an analyst to edit a record and log the change(s) to AuditLog."""
        record = self.get_object()

        if record.status == 'locked':
            return Response({'error': 'Cannot edit locked records'}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        editable_fields = [
            'activity_value', 'activity_unit', 'emission_factor', 'co2e_kg',
            'facility', 'location', 'reporting_period', 'flagged_reason'
        ]

        audit_entries = []
        changed = False
        for field in editable_fields:
            if field in data:
                old = getattr(record, field, None)
                new = data.get(field)
                # Attempt to cast numeric fields
                if field in ['activity_value', 'emission_factor', 'co2e_kg']:
                    try:
                        new_val = float(new)
                    except (TypeError, ValueError):
                        return Response({'error': f'Invalid value for {field}'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    new_val = new

                if str(old) != str(new_val):
                    audit_entries.append(AuditLog(
                        record=record,
                        changed_by=request.user if request.user.is_authenticated else None,
                        field_name=field,
                        old_value=str(old),
                        new_value=str(new_val),
                        reason=data.get('edit_reason', '')
                    ))
                    setattr(record, field, new_val)
                    changed = True

        if changed:
            record.is_edited = True
            # store the last edit_reason on the record for quick reference
            if data.get('edit_reason'):
                record.edit_reason = data.get('edit_reason')
            record.save()
            AuditLog.objects.bulk_create(audit_entries)

        return Response(NormalizedRecordSerializer(record).data)


class ClientViewSet(viewsets.ModelViewSet):
    """ViewSet for Client"""
    queryset = Client.objects.all()
    serializer_class = ClientSerializer


class DataIngestionViewSet(viewsets.ReadOnlyModelViewSet):
    """Read ingestion jobs so analysts can see file-level status."""
    queryset = DataIngestion.objects.select_related('client', 'uploaded_by').all()
    serializer_class = DataIngestionSerializer
    ordering = ['-uploaded_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        source_type = self.request.query_params.get('source_type')
        if source_type:
            queryset = queryset.filter(source_type=source_type)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset.order_by('-uploaded_at')


class RawRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose raw rows, including rows that failed validation/normalization."""
    queryset = RawRecord.objects.select_related('ingestion', 'ingestion__client').all()
    serializer_class = RawRecordSerializer
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(ingestion__client_id=client_id)

        source_type = self.request.query_params.get('source_type')
        if source_type:
            queryset = queryset.filter(ingestion__source_type=source_type)

        invalid_only = self.request.query_params.get('invalid_only', '').lower()
        if invalid_only in ['1', 'true', 'yes']:
            queryset = queryset.filter(normalizedrecord__isnull=True)

        return queryset.distinct().order_by('-created_at')

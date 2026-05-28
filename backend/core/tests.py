import json

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    AuditLog,
    Client,
    DataIngestion,
    DataQualityFlag,
    EmissionFactor,
    NormalizedRecord,
    RawRecord,
    UnitConversion,
)


class IngestionWorkflowTests(APITestCase):
    def setUp(self):
        self.client_company = Client.objects.create(name='Test Client')
        UnitConversion.objects.create(
            from_unit='MWH',
            to_unit='KWH',
            conversion_factor=1000,
            source_type='utility',
        )
        UnitConversion.objects.create(
            from_unit='GAL',
            to_unit='L',
            conversion_factor=3.78541,
            source_type='sap',
        )
        EmissionFactor.objects.create(
            activity_type='fuel',
            fuel_type='diesel',
            factor_value=2.68,
            unit='kg CO2e/L',
            source='DEFRA 2023',
            valid_from=2023,
            valid_to=2024,
        )
        EmissionFactor.objects.create(
            activity_type='electricity',
            grid_region='IN',
            factor_value=0.716,
            unit='kg CO2e/kWh',
            source='IEA 2023',
            valid_from=2023,
            valid_to=2024,
        )

    def test_sap_upload_keeps_invalid_raw_rows_visible(self):
        upload = SimpleUploadedFile(
            'sap_material_document.json',
            json.dumps({
                'PostingDate': '2024-01-15T00:00:00',
                'GoodsMovementCode': '03',
                'to_MaterialDocumentItem': [
                    {
                        'Material': 'DIESEL-001',
                        'MaterialDocumentItemText': 'Diesel Fuel',
                        'Plant': '1000',
                        'EntryUnit': 'L',
                        'QuantityInEntryUnit': '100',
                        'MaterialDocument': '4900000001',
                    },
                    {
                        'Material': 'DIESEL-001',
                        'MaterialDocumentItemText': 'Diesel Fuel',
                        'Plant': '1000',
                        'EntryUnit': 'L',
                        'QuantityInEntryUnit': 'INVALID',
                        'MaterialDocument': '4900000002',
                    },
                ],
            }).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            '/api/ingest/',
            {
                'source_type': 'sap',
                'client_id': self.client_company.id,
                'file': upload,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DataIngestion.objects.count(), 1)
        self.assertEqual(RawRecord.objects.count(), 2)
        self.assertEqual(NormalizedRecord.objects.count(), 1)
        self.assertEqual(response.data['failed_row_count'], 1)

        invalid_response = self.client.get('/api/raw-records/', {'invalid_only': 'true'})
        self.assertEqual(invalid_response.status_code, status.HTTP_200_OK)
        self.assertEqual(invalid_response.data['count'], 1)
        self.assertEqual(
            invalid_response.data['results'][0]['validation_error'],
            'Invalid or missing quantity',
        )

    def test_utility_upload_normalizes_mwh_to_kwh(self):
        upload = SimpleUploadedFile(
            'utility.csv',
            (
                b'account_number,meter_id,billing_start,billing_end,consumption,unit,demand_charge,tariff_code,facility_name\n'
                b'AC-1,MTR-1,2024-01-01,2024-02-01,2,MWh,100,HT,Mumbai Office\n'
            ),
            content_type='text/csv',
        )

        response = self.client.post(
            '/api/ingest/',
            {
                'source_type': 'utility',
                'client_id': self.client_company.id,
                'file': upload,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record = NormalizedRecord.objects.get()
        self.assertEqual(record.scope, 2)
        self.assertEqual(record.activity_unit, 'kWh')
        self.assertEqual(record.activity_value, 2000)
        self.assertAlmostEqual(record.co2e_kg, 1432)

    def test_travel_upload_flags_impossible_flight_for_review(self):
        upload = SimpleUploadedFile(
            'concur_itinerary.json',
            json.dumps({
                'ID': 'T-1',
                'UserLoginId': 'employee@example.com',
                'StartDateLocal': '2024-01-28T09:00:00',
                'Bookings': [
                    {
                        'BookingOwner': 'ConcurTravel',
                        'Segments': {
                            'Air': [
                                {
                                    'StartCityCode': 'DEL',
                                    'EndCityCode': 'DEL',
                                    'StartDateLocal': '2024-01-28T09:00:00',
                                    'Cabin': 'E',
                                    'ClassOfService': 'E',
                                }
                            ]
                        },
                    }
                ],
            }).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(
            '/api/ingest/',
            {
                'source_type': 'travel',
                'client_id': self.client_company.id,
                'file': upload,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record = NormalizedRecord.objects.get()
        self.assertEqual(record.scope, 3)
        self.assertEqual(record.status, 'flagged')
        self.assertEqual(DataQualityFlag.objects.filter(record=record).count(), 1)

        records_response = self.client.get('/api/records/')
        result = records_response.data['results'][0]
        self.assertEqual(result['flag_count'], 1)
        self.assertEqual(result['highest_severity'], 'error')

    def test_approval_creates_audit_log(self):
        upload = SimpleUploadedFile(
            'sap_material_document.json',
            json.dumps({
                'PostingDate': '2024-01-15T00:00:00',
                'GoodsMovementCode': '03',
                'to_MaterialDocumentItem': [
                    {
                        'Material': 'DIESEL-001',
                        'MaterialDocumentItemText': 'Diesel Fuel',
                        'Plant': '1000',
                        'EntryUnit': 'L',
                        'QuantityInEntryUnit': '100',
                        'MaterialDocument': '4900000001',
                    },
                ],
            }).encode('utf-8'),
            content_type='application/json',
        )
        self.client.post(
            '/api/ingest/',
            {
                'source_type': 'sap',
                'client_id': self.client_company.id,
                'file': upload,
            },
            format='multipart',
        )
        record = NormalizedRecord.objects.get()

        response = self.client.post(f'/api/records/{record.id}/approve/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertEqual(record.status, 'approved')
        self.assertEqual(AuditLog.objects.filter(record=record).count(), 1)

"""Data parsers for the selected source formats.

SAP uses the S/4HANA Material Document OData JSON shape. Travel uses the
SAP Concur Itinerary v4 shape. The small legacy parsers remain to keep older
sample files readable during local testing.
"""

from datetime import datetime


class SAPParser:
    """Parse SAP S/4HANA Material Document OData payloads."""
    
    @staticmethod
    def parse_row(row):
        """Legacy CSV row support."""
        return {
            'plant_code': row.get('plant_code', ''),
            'material_code': row.get('material_code', ''),
            'material_desc': row.get('material_desc', ''),
            'quantity': row.get('quantity', ''),
            'unit': row.get('unit', ''),
            'posting_date': row.get('posting_date', ''),
            'document_number': row.get('document_number', '')
        }

    @staticmethod
    def parse_odata_payload(payload):
        header_posting_date = payload.get('PostingDate') or payload.get('DocumentDate', '')
        items = SAPParser._extract_material_document_items(payload)

        parsed_items = []
        for item in items:
            parsed_items.append(SAPParser.parse_odata_item(item, header_posting_date))
        return parsed_items

    @staticmethod
    def parse_odata_item(item, header_posting_date=''):
        material = item.get('Material', '')
        return {
            'plant_code': item.get('Plant', ''),
            'material_code': material,
            'material_desc': item.get('MaterialDocumentItemText') or material,
            'quantity': item.get('QuantityInEntryUnit', ''),
            'unit': item.get('EntryUnit', ''),
            'posting_date': item.get('PostingDate') or header_posting_date,
            'document_number': item.get('MaterialDocument', ''),
        }
    
    @staticmethod
    def validate(row):
        try:
            float(row['quantity'])
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _extract_material_document_items(payload):
        if isinstance(payload.get('to_MaterialDocumentItem'), list):
            return payload['to_MaterialDocumentItem']
        if isinstance(payload.get('to_MaterialDocumentItem'), dict):
            return payload['to_MaterialDocumentItem'].get('results', [])
        if isinstance(payload.get('value'), list):
            return payload['value']
        if isinstance(payload.get('d'), dict):
            return payload['d'].get('results', [])
        return []


class UtilityParser:
    """Parse utility electricity CSV data"""
    
    @staticmethod
    def parse_row(row):
        return {
            'account_number': row.get('account_number', ''),
            'meter_id': row.get('meter_id', ''),
            'billing_start': row.get('billing_start', ''),
            'billing_end': row.get('billing_end', ''),
            'consumption': row.get('consumption', ''),
            'unit': row.get('unit', ''),
            'demand_charge': row.get('demand_charge', '0'),
            'tariff_code': row.get('tariff_code', ''),
            'facility_name': row.get('facility_name', '')
        }
    
    @staticmethod
    def validate(row):
        try:
            float(row['consumption'])
            return True
        except (ValueError, TypeError):
            return False


class TravelParser:
    """Parse SAP Concur Itinerary v4 JSON data."""
    
    @staticmethod
    def parse_trip(trip):
        """Legacy simplified trip support."""
        segments = []
        for segment in trip.get('segments', []):
            segments.append({
                'type': segment.get('type', ''),
                'origin': segment.get('origin', ''),
                'destination': segment.get('destination', ''),
                'departure_date': segment.get('departure_date', ''),
                'class': segment.get('class', ''),
                'city': segment.get('city', ''),
                'country': segment.get('country', ''),
                'check_in': segment.get('check_in', ''),
                'check_out': segment.get('check_out', ''),
                'nights': segment.get('nights', 0),
                'mode': segment.get('mode', ''),
                'cost_usd': segment.get('cost_usd', 0)
            })
        return {
            'trip_id': trip.get('trip_id', ''),
            'employee_id': trip.get('employee_id', ''),
            'trip_start_date': trip.get('trip_start_date', ''),
            'segments': segments
        }

    @staticmethod
    def parse_concur_itinerary(itinerary):
        segments = []
        for booking in itinerary.get('Bookings', []):
            booking_segments = booking.get('Segments', {})
            segments.extend(TravelParser._parse_concur_air_segments(booking_segments.get('Air', [])))
            segments.extend(TravelParser._parse_concur_hotel_segments(booking_segments.get('Hotel', [])))
            segments.extend(TravelParser._parse_concur_ride_segments(booking_segments.get('Ride', [])))
            segments.extend(TravelParser._parse_concur_car_segments(booking_segments.get('Car', [])))

        return {
            'trip_id': itinerary.get('ID') or itinerary.get('id') or itinerary.get('ItinLocator', ''),
            'employee_id': TravelParser._employee_identifier(itinerary),
            'trip_start_date': TravelParser._date_only(itinerary.get('StartDateLocal', '')),
            'segments': segments,
        }

    @staticmethod
    def _parse_concur_air_segments(segments):
        parsed = []
        for segment in segments:
            parsed.append({
                'type': 'flight',
                'origin': segment.get('StartCityCode', ''),
                'destination': segment.get('EndCityCode', ''),
                'departure_date': TravelParser._date_only(segment.get('StartDateLocal', '')),
                'class': TravelParser._map_concur_cabin(segment.get('Cabin') or segment.get('ClassOfService', '')),
            })
        return parsed

    @staticmethod
    def _parse_concur_hotel_segments(segments):
        parsed = []
        for segment in segments:
            parsed.append({
                'type': 'hotel',
                'city': segment.get('StartCity', '') or segment.get('StartCityCode', ''),
                'country': segment.get('StartCountry', ''),
                'check_in': TravelParser._date_only(segment.get('StartDateLocal', '')),
                'check_out': TravelParser._date_only(segment.get('EndDateLocal', '')),
                'nights': TravelParser._nights_between(
                    segment.get('StartDateLocal', ''),
                    segment.get('EndDateLocal', ''),
                ),
            })
        return parsed

    @staticmethod
    def _parse_concur_ride_segments(segments):
        parsed = []
        for segment in segments:
            parsed.append({
                'type': 'ground',
                'mode': 'taxi',
                'cost_usd': TravelParser._number(segment.get('Rate') or segment.get('TotalRate') or 0),
                'distance_km': TravelParser._miles_to_km(segment.get('Miles')),
            })
        return parsed

    @staticmethod
    def _parse_concur_car_segments(segments):
        parsed = []
        for segment in segments:
            parsed.append({
                'type': 'ground',
                'mode': 'rental_car',
                'cost_usd': TravelParser._number(segment.get('TotalRate') or 0),
                'distance_km': TravelParser._miles_to_km(segment.get('EstimatedMiles')),
            })
        return parsed

    @staticmethod
    def _employee_identifier(itinerary):
        employee = itinerary.get('Employee', {})
        return (
            itinerary.get('UserLoginId')
            or employee.get('LoginId')
            or employee.get('EmployeeId')
            or ''
        )

    @staticmethod
    def _map_concur_cabin(value):
        value = str(value).upper()
        if value in ['B', 'BUSINESS', 'C', 'J']:
            return 'business'
        return 'economy'

    @staticmethod
    def _date_only(value):
        return value[:10] if value else ''

    @staticmethod
    def _nights_between(start, end):
        try:
            start_date = datetime.fromisoformat(TravelParser._date_only(start))
            end_date = datetime.fromisoformat(TravelParser._date_only(end))
            return max((end_date - start_date).days, 0)
        except ValueError:
            return 0

    @staticmethod
    def _miles_to_km(miles):
        try:
            return float(miles) * 1.60934
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0
        

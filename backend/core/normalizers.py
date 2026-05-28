"""Normalization logic for converting raw data to standard format"""
from datetime import datetime
from .models import NormalizedRecord
from .utils import UnitConverter, EmissionFactorLookup, calculate_flight_distance


FALLBACK_FUEL_FACTORS = {
    'diesel': 2.68,
    'petrol': 2.31,
    'lpg': 1.51,
    'natural_gas': 2.04,
}

DEFAULT_GRID_REGION = 'IN'
DEFAULT_ELECTRICITY_FACTOR = 0.716
FACTOR_SOURCE_DEFRA = 'DEFRA 2023'
FACTOR_SOURCE_IEA = 'IEA 2023'

FLIGHT_FACTORS = {
    ('short', 'economy'): 0.151,
    ('short', 'business'): 0.226,
    ('long', 'economy'): 0.195,
    ('long', 'business'): 0.429,
}

HOTEL_FACTOR_GLOBAL_AVERAGE = 31.7
GROUND_FACTORS = {
    'taxi': 0.149,
    'rental_car': 0.192,
    'bus': 0.089,
}
GROUND_COST_PER_KM_USD = 2


class Normalizer:
    """Normalize raw data into standard format"""
    
    @staticmethod
    def normalize_sap(raw_record, client):
        """Normalize SAP fuel data"""
        raw_data = raw_record.raw_data
        
        material_desc = raw_data.get('material_desc', '').lower()
        fuel_type = Normalizer._infer_fuel_type(material_desc)
        used_fallback_fuel_type = fuel_type is None
        fuel_type = fuel_type or 'diesel'

        quantity = float(raw_data['quantity'])
        unit = raw_data['unit'].upper()

        if fuel_type == 'natural_gas' and unit == 'M3':
            unit = 'm3'
        elif unit == 'GAL':
            quantity = UnitConverter.convert(quantity, 'GAL', 'L', 'sap')
            unit = 'L'
        elif unit == 'KG':
            quantity = UnitConverter.convert(quantity, 'KG', 'L', 'sap')
            unit = 'L'
        elif unit == 'M3':
            quantity = UnitConverter.convert(quantity, 'M3', 'L', 'sap')
            unit = 'L'
        
        factor, source = EmissionFactorLookup.get_factor('fuel', fuel_type=fuel_type)
        if factor is None:
            factor = FALLBACK_FUEL_FACTORS[fuel_type]
            source = FACTOR_SOURCE_DEFRA
        
        co2e_kg = quantity * factor
        reporting_period = Normalizer._month_from_date(
            raw_data.get('posting_date', ''),
            ['%Y%m%d', '%Y-%m-%d'],
        )
        status = 'flagged' if used_fallback_fuel_type else 'pending'
        flagged_reason = 'Fuel type could not be inferred from material description' if used_fallback_fuel_type else None
        
        return NormalizedRecord.objects.create(
            raw_record=raw_record,
            client=client,
            scope=1,
            activity_type='fuel',
            activity_value=quantity,
            activity_unit=unit,
            emission_factor=factor,
            emission_factor_source=source,
            co2e_kg=co2e_kg,
            facility=f"Plant {raw_data.get('plant_code', 'Unknown')}",
            location='Unknown',
            reporting_period=reporting_period,
            status=status,
            flagged_reason=flagged_reason
        )
    
    @staticmethod
    def normalize_utility(raw_record, client):
        """Normalize utility electricity data"""
        raw_data = raw_record.raw_data
        
        consumption = float(raw_data['consumption'])
        unit = raw_data['unit'].upper()
        
        if unit == 'MWH':
            consumption = UnitConverter.convert(consumption, 'MWH', 'KWH', 'utility')
            unit = 'kWh'
        
        factor, source = EmissionFactorLookup.get_factor(
            'electricity',
            grid_region=DEFAULT_GRID_REGION,
        )
        if factor is None:
            factor = DEFAULT_ELECTRICITY_FACTOR
            source = FACTOR_SOURCE_IEA
        
        co2e_kg = consumption * factor
        reporting_period = Normalizer._month_from_date(
            raw_data.get('billing_start', ''),
            ['%Y-%m-%d'],
        )
        
        return NormalizedRecord.objects.create(
            raw_record=raw_record,
            client=client,
            scope=2,
            activity_type='electricity',
            activity_value=consumption,
            activity_unit=unit,
            emission_factor=factor,
            emission_factor_source=source,
            co2e_kg=co2e_kg,
            facility=raw_data.get('facility_name', 'Unknown'),
            location='Unknown',
            reporting_period=reporting_period,
            status='pending'
        )
    
    @staticmethod
    def normalize_travel(raw_record, client):
        """Normalize travel data"""
        raw_data = raw_record.raw_data
        segments = raw_data.get('segments', [])
        
        normalized_records = []
        
        for segment in segments:
            segment_type = segment.get('type', '')
            
            if segment_type == 'flight':
                origin = segment.get('origin', '')
                destination = segment.get('destination', '')
                distance = calculate_flight_distance(origin, destination)
                
                flight_class = segment.get('class', 'economy')
                haul = 'long' if distance > 3700 else 'short'
                factor = FLIGHT_FACTORS.get((haul, flight_class), FLIGHT_FACTORS[(haul, 'economy')])
                co2e_kg = distance * factor
                
                record = NormalizedRecord.objects.create(
                    raw_record=raw_record,
                    client=client,
                    scope=3,
                    activity_type='flight',
                    activity_value=distance,
                    activity_unit='km',
                    emission_factor=factor,
                    emission_factor_source=FACTOR_SOURCE_DEFRA,
                    co2e_kg=co2e_kg,
                    facility=f'{origin} -> {destination}',
                    location='Travel',
                    reporting_period=Normalizer._travel_reporting_period(raw_data),
                    status='pending'
                )
                normalized_records.append(record)
            
            elif segment_type == 'hotel':
                nights = segment.get('nights', 0)
                factor = HOTEL_FACTOR_GLOBAL_AVERAGE
                co2e_kg = nights * factor
                
                record = NormalizedRecord.objects.create(
                    raw_record=raw_record,
                    client=client,
                    scope=3,
                    activity_type='hotel',
                    activity_value=nights,
                    activity_unit='nights',
                    emission_factor=factor,
                    emission_factor_source=FACTOR_SOURCE_DEFRA,
                    co2e_kg=co2e_kg,
                    facility=segment.get('city', 'Unknown'),
                    location='Travel',
                    reporting_period=Normalizer._travel_reporting_period(raw_data),
                    status='pending'
                )
                normalized_records.append(record)
            
            elif segment_type == 'ground':
                actual_distance = segment.get('distance_km', 0)
                cost = segment.get('cost_usd', 0)
                mode = segment.get('mode', 'taxi')

                estimated_distance = actual_distance or (cost / GROUND_COST_PER_KM_USD if cost > 0 else 0)
                factor = GROUND_FACTORS.get(mode, GROUND_FACTORS['taxi'])
                co2e_kg = estimated_distance * factor
                
                record = NormalizedRecord.objects.create(
                    raw_record=raw_record,
                    client=client,
                    scope=3,
                    activity_type='ground',
                    activity_value=estimated_distance,
                    activity_unit='km',
                    emission_factor=factor,
                    emission_factor_source=FACTOR_SOURCE_DEFRA,
                    co2e_kg=co2e_kg,
                    facility=mode,
                    location='Travel',
                    reporting_period=Normalizer._travel_reporting_period(raw_data),
                    status='pending'
                )
                normalized_records.append(record)
        
        return normalized_records

    @staticmethod
    def _infer_fuel_type(material_desc):
        if 'diesel' in material_desc:
            return 'diesel'
        if 'petrol' in material_desc:
            return 'petrol'
        if 'lpg' in material_desc:
            return 'lpg'
        if 'natural gas' in material_desc or 'ng' in material_desc:
            return 'natural_gas'
        return None

    @staticmethod
    def _month_from_date(value, formats):
        if value and len(value) >= 10 and value[4] == '-' and value[7] == '-':
            return value[:7]

        for date_format in formats:
            try:
                return datetime.strptime(value, date_format).strftime('%Y-%m')
            except (TypeError, ValueError):
                continue
        return 'Unknown'

    @staticmethod
    def _travel_reporting_period(raw_data):
        trip_start_date = raw_data.get('trip_start_date')
        return trip_start_date[:7] if trip_start_date else 'Unknown'

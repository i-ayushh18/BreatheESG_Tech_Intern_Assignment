"""Utility functions for calculations and conversions"""
import math
from .models import UnitConversion, EmissionFactor


# Airport coordinates (simplified for MVP)
AIRPORT_COORDINATES = {
    'DEL': {'name': 'Indira Gandhi International', 'lat': 28.5562, 'lon': 77.1000},
    'BOM': {'name': 'Chhatrapati Shivaji International', 'lat': 19.0896, 'lon': 72.8656},
    'BLR': {'name': 'Kempegowda International', 'lat': 13.1986, 'lon': 77.7066},
    'SFO': {'name': 'San Francisco International', 'lat': 37.6213, 'lon': -122.3790},
    'CCU': {'name': 'Netaji Subhas Chandra Bose International', 'lat': 22.6547, 'lon': 88.4467},
    'HYD': {'name': 'Rajiv Gandhi International', 'lat': 17.2403, 'lon': 78.4294}
}


def haversine(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points on Earth in kilometers"""
    R = 6371  # Earth radius in km
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def calculate_flight_distance(origin_code, destination_code):
    """Calculate flight distance using airport coordinates"""
    origin = AIRPORT_COORDINATES.get(origin_code)
    dest = AIRPORT_COORDINATES.get(destination_code)
    if origin and dest:
        return haversine(origin['lat'], origin['lon'], dest['lat'], dest['lon'])

    # Do not silently return 0 for unknown airports — raise to surface bad data
    missing = []
    if not origin:
        missing.append(origin_code)
    if not dest:
        missing.append(destination_code)
    raise ValueError(f'Unknown airport code(s): {",".join(missing)}')


class UnitConverter:
    """Handle unit conversions for different source types"""
    
    @staticmethod
    def convert(value, from_unit, to_unit, source_type):
        try:
            conversion = UnitConversion.objects.get(
                from_unit=from_unit.upper(),
                to_unit=to_unit.upper(),
                source_type=source_type
            )
            return value * conversion.conversion_factor
        except UnitConversion.DoesNotExist:
            # If no conversion found, assume 1:1
            return value


class EmissionFactorLookup:
    """Lookup emission factors for different activity types"""
    
    @staticmethod
    def get_factor(activity_type, fuel_type=None, grid_region=None, transport_mode=None):
        try:
            factor = EmissionFactor.objects.get(
                activity_type=activity_type,
                fuel_type=fuel_type,
                grid_region=grid_region,
                transport_mode=transport_mode
            )
            return factor.factor_value, factor.source
        except EmissionFactor.DoesNotExist:
            return None, None

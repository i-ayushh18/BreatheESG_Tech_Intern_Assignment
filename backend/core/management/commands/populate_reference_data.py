from django.core.management.base import BaseCommand
from core.models import UnitConversion, EmissionFactor, Client


class Command(BaseCommand):
    help = 'Populate reference data tables (UnitConversion, EmissionFactor, Client)'

    def handle(self, *args, **options):
        self.stdout.write('Populating reference data...')
        
        # Create default client
        client, created = Client.objects.get_or_create(
            name='Demo Client',
            defaults={}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created client: {client.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Client already exists: {client.name}'))
        
        # Populate Unit Conversions
        unit_conversions = [
            # SAP conversions
            {'from_unit': 'GAL', 'to_unit': 'L', 'conversion_factor': 3.78541, 'source_type': 'sap'},
            # Note: mass-to-volume conversions vary by fuel type (diesel, petrol, lpg).
            # The model currently doesn't include fuel-specific conversions; avoid a
            # single KG->L mapping which would be incorrect for many fuels.
            {'from_unit': 'M3', 'to_unit': 'L', 'conversion_factor': 1000.0, 'source_type': 'sap'},
            
            # Utility conversions
            {'from_unit': 'MWH', 'to_unit': 'KWH', 'conversion_factor': 1000.0, 'source_type': 'utility'},
        ]
        
        for conv in unit_conversions:
            obj, created = UnitConversion.objects.get_or_create(
                from_unit=conv['from_unit'],
                to_unit=conv['to_unit'],
                source_type=conv['source_type'],
                defaults={'conversion_factor': conv['conversion_factor']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created unit conversion: {conv["from_unit"]} -> {conv["to_unit"]} ({conv["conversion_factor"]})'))
            else:
                self.stdout.write(self.style.WARNING(f'Unit conversion already exists: {conv["from_unit"]} -> {conv["to_unit"]}'))
        
        # Populate Emission Factors - Fuel (Scope 1)
        fuel_factors = [
            {'activity_type': 'fuel', 'fuel_type': 'diesel', 'factor_value': 2.68, 'unit': 'kg CO2e/L', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'fuel', 'fuel_type': 'petrol', 'factor_value': 2.31, 'unit': 'kg CO2e/L', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'fuel', 'fuel_type': 'lpg', 'factor_value': 1.51, 'unit': 'kg CO2e/L', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'fuel', 'fuel_type': 'natural_gas', 'factor_value': 2.04, 'unit': 'kg CO2e/m³', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
        ]
        
        for factor in fuel_factors:
            obj, created = EmissionFactor.objects.get_or_create(
                activity_type=factor['activity_type'],
                fuel_type=factor['fuel_type'],
                grid_region=None,
                transport_mode=None,
                defaults={
                    'factor_value': factor['factor_value'],
                    'unit': factor['unit'],
                    'source': factor['source'],
                    'valid_from': factor['valid_from'],
                    'valid_to': factor['valid_to']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created emission factor: {factor["activity_type"]} - {factor["fuel_type"]} ({factor["factor_value"]})'))
            else:
                self.stdout.write(self.style.WARNING(f'Emission factor already exists: {factor["activity_type"]} - {factor["fuel_type"]}'))
        
        # Populate Emission Factors - Electricity (Scope 2)
        electricity_factors = [
            {'activity_type': 'electricity', 'grid_region': 'IN', 'factor_value': 0.716, 'unit': 'kg CO2e/kWh', 'source': 'IEA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'electricity', 'grid_region': 'US', 'factor_value': 0.386, 'unit': 'kg CO2e/kWh', 'source': 'IEA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'electricity', 'grid_region': 'UK', 'factor_value': 0.207, 'unit': 'kg CO2e/kWh', 'source': 'IEA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'electricity', 'grid_region': 'FR', 'factor_value': 0.052, 'unit': 'kg CO2e/kWh', 'source': 'IEA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'electricity', 'grid_region': 'CN', 'factor_value': 0.581, 'unit': 'kg CO2e/kWh', 'source': 'IEA 2023', 'valid_from': 2023, 'valid_to': 2024},
        ]
        
        for factor in electricity_factors:
            obj, created = EmissionFactor.objects.get_or_create(
                activity_type=factor['activity_type'],
                fuel_type=None,
                grid_region=factor['grid_region'],
                transport_mode=None,
                defaults={
                    'factor_value': factor['factor_value'],
                    'unit': factor['unit'],
                    'source': factor['source'],
                    'valid_from': factor['valid_from'],
                    'valid_to': factor['valid_to']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created emission factor: {factor["activity_type"]} - {factor["grid_region"]} ({factor["factor_value"]})'))
            else:
                self.stdout.write(self.style.WARNING(f'Emission factor already exists: {factor["activity_type"]} - {factor["grid_region"]}'))
        
        # Populate Emission Factors - Travel (Scope 3)
        travel_factors = [
            {'activity_type': 'flight', 'transport_mode': 'short_haul_economy', 'factor_value': 0.151, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'flight', 'transport_mode': 'short_haul_business', 'factor_value': 0.226, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'flight', 'transport_mode': 'long_haul_economy', 'factor_value': 0.195, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'flight', 'transport_mode': 'long_haul_business', 'factor_value': 0.429, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'hotel', 'transport_mode': 'global_average', 'factor_value': 31.7, 'unit': 'kg CO2e/room-night', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'hotel', 'transport_mode': 'india', 'factor_value': 25.0, 'unit': 'kg CO2e/room-night', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'hotel', 'transport_mode': 'usa', 'factor_value': 35.8, 'unit': 'kg CO2e/room-night', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'hotel', 'transport_mode': 'uk', 'factor_value': 21.4, 'unit': 'kg CO2e/room-night', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'ground', 'transport_mode': 'taxi', 'factor_value': 0.149, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'ground', 'transport_mode': 'rental_car', 'factor_value': 0.192, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'ground', 'transport_mode': 'bus', 'factor_value': 0.089, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
            {'activity_type': 'ground', 'transport_mode': 'metro', 'factor_value': 0.041, 'unit': 'kg CO2e/km', 'source': 'DEFRA 2023', 'valid_from': 2023, 'valid_to': 2024},
        ]
        
        for factor in travel_factors:
            obj, created = EmissionFactor.objects.get_or_create(
                activity_type=factor['activity_type'],
                fuel_type=None,
                grid_region=None,
                transport_mode=factor['transport_mode'],
                defaults={
                    'factor_value': factor['factor_value'],
                    'unit': factor['unit'],
                    'source': factor['source'],
                    'valid_from': factor['valid_from'],
                    'valid_to': factor['valid_to']
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created emission factor: {factor["activity_type"]} - {factor["transport_mode"]} ({factor["factor_value"]})'))
            else:
                self.stdout.write(self.style.WARNING(f'Emission factor already exists: {factor["activity_type"]} - {factor["transport_mode"]}'))
        
        self.stdout.write(self.style.SUCCESS('Reference data population completed successfully!'))

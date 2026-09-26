"""
Data Intelligence Agent
Collects environmental, geotechnical, demographic, and infrastructural telemetry
for operational zones without requiring manual 20-slider user input.
"""
import logging
from services.data_service import DataIntelligenceService
from services.location_service import LocationService

logger = logging.getLogger(__name__)

class DataAgent:
    def __init__(self):
        self.data_service = DataIntelligenceService()
        self.location_service = LocationService()

    def generate_zone_telemetry(self, normalized_loc, custom_zones=None, weather_override=None):
        """
        Partitions the location into operational zones and gathers 20-feature vectors.
        """
        zones = custom_zones or self.location_service.generate_operational_zones(normalized_loc)
        location_coords = f"{normalized_loc['latitude']}, {normalized_loc['longitude']}"

        enriched_zones = []
        weather_summary = None

        for z in zones:
            feats, weather = self.data_service.synthesize_zone_features(z, location_coords, weather_override=weather_override)
            if weather_summary is None:
                weather_summary = weather

            zone_dict = dict(z)
            zone_dict["feats"] = feats
            enriched_zones.append(zone_dict)

        logger.info(f"Synthesized telemetry for {len(enriched_zones)} operational zones via Data Intelligence Agent.")
        return enriched_zones, weather_summary

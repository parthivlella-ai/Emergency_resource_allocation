"""
Model Context Protocol (MCP) Provider Service
Provides standard MCP tool manifests and execution handlers for external AI systems,
allowing seamless interoperability with MCP clients for weather, geocoding, and emergency dispatch.
"""
import logging
from services.data_service import WeatherProvider, TopographyProvider
from services.location_service import LocationService

logger = logging.getLogger(__name__)

MCP_TOOL_MANIFEST = [
    {
        "name": "get_live_weather_telemetry",
        "description": "Fetches current precipitation, wind velocity, and temperature from Open-Meteo live API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Target decimal latitude"},
                "longitude": {"type": "number", "description": "Target decimal longitude"}
            },
            "required": ["latitude", "longitude"]
        }
    },
    {
        "name": "geocode_emergency_location",
        "description": "Resolves location names into geodetic coordinates using OpenStreetMap Nominatim.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "City or operational zone name"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "audit_resource_shortage",
        "description": "Evaluates required versus available emergency inventory and identifies supply deficits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "required_assets": {"type": "object", "description": "Dict of requested equipment counts"},
                "available_assets": {"type": "object", "description": "Dict of available stock"}
            },
            "required": ["required_assets", "available_assets"]
        }
    }
]

class MCPService:
    def __init__(self):
        self.weather = WeatherProvider()
        self.topo = TopographyProvider()
        self.location = LocationService()

    def get_manifest(self):
        """Returns the registered MCP tool definitions."""
        return {
            "protocol_version": "2024-11-05",
            "server_name": "Emergency-Resource-Allocation-MCP-Engine",
            "tools": MCP_TOOL_MANIFEST
        }

    def execute_tool(self, tool_name, arguments):
        """Dispatches an MCP tool call to the appropriate internal provider."""
        logger.info(f"Executing MCP tool call: {tool_name} with args {arguments}")
        if tool_name == "get_live_weather_telemetry":
            lat = float(arguments.get("latitude", 16.5))
            lon = float(arguments.get("longitude", 80.6))
            data = self.weather.get_weather_data(lat, lon)
            return {"content": [{"type": "text", "text": str(data)}]}
        elif tool_name == "geocode_emergency_location":
            query = arguments.get("query", "Vijayawada")
            data = self.location.normalize_location(query)
            return {"content": [{"type": "text", "text": str(data)}]}
        elif tool_name == "audit_resource_shortage":
            req = arguments.get("required_assets", {})
            avail = arguments.get("available_assets", {})
            shortages = {}
            for k, v in req.items():
                if v > avail.get(k, 0):
                    shortages[k] = v - avail.get(k, 0)
            return {"content": [{"type": "text", "text": str({"shortages": shortages, "has_shortage": len(shortages) > 0})}]}
        else:
            return {"error": f"Unknown MCP tool: {tool_name}"}

import logging
import math
import requests
import json
from typing import List, Dict, Any, Union
from mcp.server.fastmcp import FastMCP
from toolsets.servers.cache import ToolsetCache

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Geo_API")

mcp = FastMCP("Geo")

# Define API endpoints
NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSRM_URL = "https://router.project-osrm.org"

# Create caches for different types of operations
# 1. Geocoding operations - deterministic with long-term persistence
geocode_cache = ToolsetCache(
    name="geo.geocoding",
    deterministic=True,  # Results won't change for the same input
    max_size=5000,  # Store up to 5000 geocoding results
)

# 2. Route finding - non-deterministic (traffic conditions change)
route_cache = ToolsetCache(
    name="geo.routing",
    deterministic=False,  # Routes can change based on traffic conditions
    expiry_seconds=1800,  # Cache for 30 minutes
    max_size=500,  # Store up to 500 routes
)

# 3. Distance calculations - deterministic (mathematical formula)
distance_cache = ToolsetCache(
    name="geo.distance",
    deterministic=True,  # Distance calculations are deterministic
    max_size=10000,  # Store up to 10000 distance calculations
)

# 4. POI searches - semi-deterministic but POIs can change
poi_cache = ToolsetCache(
    name="geo.pois",
    deterministic=False,  # POIs can change over time
    expiry_seconds=86400,  # Cache for 24 hours
    max_size=1000,  # Store up to 1000 POI searches
)


@mcp.tool()
@geocode_cache.cached
def geocode(
    query: str, limit: int = 5, country_codes: str = ""
) -> List[Dict[str, Any]]:
    """
    Search for a location by name and return its geographic coordinates.

    Parameters:
    - query: Location name or address to search for
    - limit: Maximum number of results to return (1-10)
    - country_codes: Limit results to specific countries (comma-separated ISO 3166-1alpha2 codes, e.g., 'us,ca,mx')

    Returns a list of location details including coordinates.
    """
    logger.debug(f"Geocoding query: '{query}'")

    limit = min(max(1, limit), 10)  # Limit between 1 and 10

    params = {
        "q": query,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
    }

    if country_codes:
        params["countrycodes"] = country_codes

    url = f"{NOMINATIM_URL}/search"
    headers = {
        "User-Agent": "GeoAPI/1.0 (MCP Tool; https://github.com/user/mcp-geo-tool)",
        "Accept": "application/json",
    }

    try:
        logger.debug(f"Request URL: {url}, Params: {params}")
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()

        results = response.json()
        logger.debug(
            f"Raw response: {json.dumps(results[:2], indent=2) if len(results) > 1 else json.dumps(results, indent=2)}"
        )

        formatted_results = []
        for result in results:
            formatted_result = {
                "place_id": result.get("place_id"),
                "name": result.get("display_name"),
                "latitude": float(result.get("lat")),
                "longitude": float(result.get("lon")),
                "type": result.get("type"),
                "importance": result.get("importance"),
                "address": result.get("address", {}),
                "tags": result.get("extratags", {}),
            }
            formatted_results.append(formatted_result)

        logger.info(f"Found {len(formatted_results)} locations for query: '{query}'")
        return formatted_results

    except requests.exceptions.RequestException as e:
        logger.error(f"Geocoding request failed: {str(e)}", exc_info=True)
        raise ValueError(f"Geocoding request failed: {str(e)}")

    except Exception as e:
        logger.error(f"Geocoding failed: {str(e)}", exc_info=True)
        raise ValueError(f"Geocoding failed: {str(e)}")


@mcp.tool()
@geocode_cache.cached
def reverse_geocode(
    latitude: float, longitude: float, zoom: int = 18
) -> Dict[str, Any]:
    """
    Get address and location details from latitude and longitude coordinates.

    Parameters:
    - latitude: Latitude coordinate (decimal degrees)
    - longitude: Longitude coordinate (decimal degrees)
    - zoom: Zoom level for detail (1-18, higher means more detail)

    Returns detailed location information for the given coordinates.
    """
    logger.debug(f"Reverse geocoding coordinates: ({latitude}, {longitude})")

    zoom = min(max(1, zoom), 18)  # Limit between 1 and 18

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "json",
        "zoom": zoom,
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
    }

    url = f"{NOMINATIM_URL}/reverse"
    headers = {
        "User-Agent": "GeoAPI/1.0 (MCP Tool; https://github.com/user/mcp-geo-tool)",
        "Accept": "application/json",
    }

    try:
        logger.debug(f"Request URL: {url}, Params: {params}")
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()

        result = response.json()
        logger.debug(f"Raw response: {json.dumps(result, indent=2)}")

        # Handle error case where no result is found
        if "error" in result:
            logger.warning(f"No location found: {result.get('error')}")
            raise ValueError(f"No location found: {result.get('error')}")

        formatted_result = {
            "place_id": result.get("place_id"),
            "name": result.get("display_name"),
            "latitude": float(result.get("lat")),
            "longitude": float(result.get("lon")),
            "type": result.get("type"),
            "address": result.get("address", {}),
            "tags": result.get("extratags", {}),
            "osm_id": result.get("osm_id"),
            "osm_type": result.get("osm_type"),
        }

        logger.info(f"Found location: '{formatted_result['name']}'")
        return formatted_result

    except requests.exceptions.RequestException as e:
        logger.error(f"Reverse geocoding request failed: {str(e)}", exc_info=True)
        raise ValueError(f"Reverse geocoding request failed: {str(e)}")

    except Exception as e:
        logger.error(f"Reverse geocoding failed: {str(e)}", exc_info=True)
        raise ValueError(f"Reverse geocoding failed: {str(e)}")


@mcp.tool()
@poi_cache.cached
def find_nearby_pois(
    latitude: float,
    longitude: float,
    radius: int = 1000,
    category: str = "all",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Find points of interest (POIs) near a specific location.

    Parameters:
    - latitude: Latitude coordinate (decimal degrees)
    - longitude: Longitude coordinate (decimal degrees)
    - radius: Search radius in meters (max 5000)
    - category: POI category to search for ('all', 'restaurant', 'hotel', 'shop', 'transport',
                'tourism', 'entertainment', 'education', 'health', 'finance')
    - limit: Maximum number of results to return (max 100)

    Returns a list of nearby POIs with their details.
    """
    logger.debug(
        f"Finding POIs near ({latitude}, {longitude}) within {radius}m, category: {category}"
    )

    # Limit values to reasonable ranges
    radius = min(max(100, radius), 5000)  # Limit between 100 and 5000 meters
    limit = min(max(1, limit), 100)  # Limit between 1 and 100 results

    # Map category to OSM tags
    category_tags = {
        "restaurant": [
            "amenity=restaurant",
            "amenity=cafe",
            "amenity=fast_food",
            "amenity=bar",
            "amenity=pub",
        ],
        "hotel": [
            "tourism=hotel",
            "tourism=hostel",
            "tourism=guest_house",
            "tourism=apartment",
            "tourism=motel",
        ],
        "shop": ["shop"],
        "transport": [
            "highway=bus_stop",
            "railway=station",
            "amenity=parking",
            "amenity=fuel",
            "aeroway=aerodrome",
        ],
        "tourism": [
            "tourism=attraction",
            "tourism=viewpoint",
            "tourism=museum",
            "leisure=park",
        ],
        "entertainment": [
            "leisure=stadium",
            "leisure=sports_centre",
            "amenity=theatre",
            "amenity=cinema",
        ],
        "education": [
            "amenity=school",
            "amenity=university",
            "amenity=college",
            "amenity=library",
        ],
        "health": [
            "amenity=hospital",
            "amenity=doctors",
            "amenity=pharmacy",
            "amenity=dentist",
        ],
        "finance": ["amenity=bank", "amenity=atm"],
    }

    # Build the Overpass QL query
    overpass_query = f"""
    [out:json][timeout:25];
    (
    """

    if category.lower() == "all":
        # Search for all common POI types
        overpass_query += f"""
        node["amenity"](around:{radius},{latitude},{longitude});
        node["shop"](around:{radius},{latitude},{longitude});
        node["tourism"](around:{radius},{latitude},{longitude});
        node["leisure"](around:{radius},{latitude},{longitude});
        way["amenity"](around:{radius},{latitude},{longitude});
        way["shop"](around:{radius},{latitude},{longitude});
        way["tourism"](around:{radius},{latitude},{longitude});
        way["leisure"](around:{radius},{latitude},{longitude});
        """
    elif category.lower() in category_tags:
        # Search for specific category
        for tag in category_tags[category.lower()]:
            if "=" in tag:
                key, value = tag.split("=")
                overpass_query += f"""
                node["{key}"="{value}"](around:{radius},{latitude},{longitude});
                way["{key}"="{value}"](around:{radius},{latitude},{longitude});
                """
            else:
                overpass_query += f"""
                node["{tag}"](around:{radius},{latitude},{longitude});
                way["{tag}"](around:{radius},{latitude},{longitude});
                """
    else:
        # Search for generic amenities if category not recognized
        overpass_query += f"""
        node["amenity"](around:{radius},{latitude},{longitude});
        way["amenity"](around:{radius},{latitude},{longitude});
        """

    overpass_query += f"""
    );
    out body {limit};
    >;
    out skel qt;
    """

    try:
        logger.debug(f"Overpass query: {overpass_query}")

        # Send request to Overpass API
        response = requests.post(
            OVERPASS_URL,
            data={"data": overpass_query},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

        data = response.json()
        logger.debug(f"Raw response elements count: {len(data.get('elements', []))}")

        # Process results
        results = []
        element_count = 0

        for element in data.get("elements", []):
            if element_count >= limit:
                break

            # Only process nodes and ways with tags
            if "tags" not in element:
                continue

            tags = element.get("tags", {})

            # Skip elements without a name unless they have useful tags
            if "name" not in tags and not any(
                key in tags for key in ["amenity", "shop", "tourism", "leisure"]
            ):
                continue

            # Get coordinates
            coords = {}
            if element["type"] == "node":
                coords = {"lat": element.get("lat"), "lon": element.get("lon")}
            elif element["type"] == "way" and "center" in element:
                coords = {
                    "lat": element.get("center", {}).get("lat"),
                    "lon": element.get("center", {}).get("lon"),
                }
            else:
                continue  # Skip if we can't determine coordinates

            poi = {
                "id": element.get("id"),
                "type": element.get("type"),
                "name": tags.get("name", "Unnamed Location"),
                "latitude": coords["lat"],
                "longitude": coords["lon"],
                "tags": tags,
                "category": category,
            }

            # Add specific details based on common tags
            if "amenity" in tags:
                poi["amenity_type"] = tags["amenity"]
            if "shop" in tags:
                poi["shop_type"] = tags["shop"]
            if "tourism" in tags:
                poi["tourism_type"] = tags["tourism"]
            if "cuisine" in tags:
                poi["cuisine"] = tags["cuisine"]
            if "opening_hours" in tags:
                poi["opening_hours"] = tags["opening_hours"]
            if "phone" in tags:
                poi["phone"] = tags["phone"]
            if "website" in tags:
                poi["website"] = tags["website"]

            results.append(poi)
            element_count += 1

        logger.info(f"Found {len(results)} POIs near ({latitude}, {longitude})")
        return results

    except requests.exceptions.RequestException as e:
        logger.error(f"POI search request failed: {str(e)}", exc_info=True)
        raise ValueError(f"POI search request failed: {str(e)}")

    except Exception as e:
        logger.error(f"POI search failed: {str(e)}", exc_info=True)
        raise ValueError(f"POI search failed: {str(e)}")


@mcp.tool()
@route_cache.cached
def get_route(
    from_lat: float, from_lon: float, to_lat: float, to_lon: float, mode: str = "car"
) -> Dict[str, Any]:
    """
    Get a route between two points with turn-by-turn directions.

    Parameters:
    - from_lat: Starting point latitude
    - from_lon: Starting point longitude
    - to_lat: Destination latitude
    - to_lon: Destination longitude
    - mode: Transportation mode ('car', 'bicycle', 'foot')

    Returns route details including distance, duration, and directions.
    """
    logger.debug(
        f"Finding route from ({from_lat}, {from_lon}) to ({to_lat}, {to_lon}), mode: {mode}"
    )

    # Map mode to OSRM profile
    if mode.lower() not in ["car", "bicycle", "foot"]:
        mode = "car"  # Default to car if invalid mode

    profile = {"car": "driving", "bicycle": "cycling", "foot": "walking"}.get(
        mode.lower(), "driving"
    )

    # Use OSRM public API
    osrm_url = f"{OSRM_URL}/route/v1/{profile}/{from_lon},{from_lat};{to_lon},{to_lat}"

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "annotations": "true",
    }

    try:
        logger.debug(f"Request URL: {osrm_url}")
        response = requests.get(osrm_url, params=params)
        response.raise_for_status()

        data = response.json()
        logger.debug(f"Raw response code: {data.get('code')}")

        if data.get("code") != "Ok" or not data.get("routes"):
            logger.warning(f"No route found: {data.get('message', 'Unknown error')}")
            raise ValueError(f"No route found: {data.get('message', 'Unknown error')}")

        route = data["routes"][0]

        # Process the steps to create readable directions
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                steps.append(
                    {
                        "instruction": step.get("maneuver", {}).get("instruction", ""),
                        "distance": step.get("distance", 0),
                        "duration": step.get("duration", 0),
                        "name": step.get("name", ""),
                        "type": step.get("maneuver", {}).get("type", ""),
                        "modifier": step.get("maneuver", {}).get("modifier", ""),
                    }
                )

        result = {
            "distance": route.get("distance", 0),  # meters
            "duration": route.get("duration", 0),  # seconds
            "route_geometry": route.get("geometry", {}),
            "steps": steps,
            "summary": route.get("summary", ""),
            "start_point": {"latitude": from_lat, "longitude": from_lon},
            "end_point": {"latitude": to_lat, "longitude": to_lon},
            "mode": mode,
        }

        # Add human-readable distance and duration
        if "distance" in result:
            if result["distance"] >= 1000:
                result["distance_text"] = f"{result['distance']/1000:.1f} km"
            else:
                result["distance_text"] = f"{int(result['distance'])} m"

        if "duration" in result:
            hours = result["duration"] // 3600
            minutes = (result["duration"] % 3600) // 60
            if hours > 0:
                result["duration_text"] = f"{int(hours)}h {int(minutes)}min"
            else:
                result["duration_text"] = f"{int(minutes)}min"

        logger.info(
            f"Found route: {result['distance_text']}, {result['duration_text']}"
        )
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"Routing request failed: {str(e)}", exc_info=True)
        raise ValueError(f"Routing request failed: {str(e)}")

    except Exception as e:
        logger.error(f"Routing failed: {str(e)}", exc_info=True)
        raise ValueError(f"Routing failed: {str(e)}")


@mcp.tool()
@distance_cache.cached
def get_distance(
    from_lat: float, from_lon: float, to_lat: float, to_lon: float
) -> Dict[str, Any]:
    """
    Calculate the direct (as-the-crow-flies) distance between two points.

    Parameters:
    - from_lat: Starting point latitude
    - from_lon: Starting point longitude
    - to_lat: Destination latitude
    - to_lon: Destination longitude

    Returns the distance in various units (meters, kilometers, miles).
    """
    logger.debug(
        f"Calculating distance from ({from_lat}, {from_lon}) to ({to_lat}, {to_lon})"
    )

    try:
        # Earth's radius in kilometers
        R = 6371.0

        # Convert latitude and longitude from degrees to radians
        lat1 = math.radians(from_lat)
        lon1 = math.radians(from_lon)
        lat2 = math.radians(to_lat)
        lon2 = math.radians(to_lon)

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        # Distance in kilometers
        distance_km = R * c

        # Convert to other units
        distance_m = distance_km * 1000
        distance_miles = distance_km * 0.621371

        result = {
            "distance_meters": round(distance_m, 2),
            "distance_kilometers": round(distance_km, 2),
            "distance_miles": round(distance_miles, 2),
            "from_point": {"latitude": from_lat, "longitude": from_lon},
            "to_point": {"latitude": to_lat, "longitude": to_lon},
        }

        logger.info(f"Calculated distance: {result['distance_kilometers']} km")
        return result

    except Exception as e:
        logger.error(f"Distance calculation failed: {str(e)}", exc_info=True)
        raise ValueError(f"Distance calculation failed: {str(e)}")


# @mcp.tool()
# def get_cache_stats() -> Dict[str, Any]:
#     """
#     Get statistics about the Geo API caches.

#     Returns information about cache usage, hits, misses, etc.
#     """
#     return {
#         "geocode_cache": geocode_cache.get_stats(),
#         "route_cache": route_cache.get_stats(),
#         "distance_cache": distance_cache.get_stats(),
#         "poi_cache": poi_cache.get_stats(),
#     }


# @mcp.tool()
# def clear_caches(cache_name: str = "all") -> Dict[str, int]:
#     """
#     Clear one or all caches.

#     Parameters:
#     - cache_name: Which cache to clear ('all', 'geocode', 'route', 'distance', 'poi')

#     Returns the number of items cleared from each cache.
#     """
#     results = {}

#     if cache_name.lower() in ["all", "geocode"]:
#         results["geocode"] = geocode_cache.clear()

#     if cache_name.lower() in ["all", "route"]:
#         results["route"] = route_cache.clear()

#     if cache_name.lower() in ["all", "distance"]:
#         results["distance"] = distance_cache.clear()

#     if cache_name.lower() in ["all", "poi"]:
#         results["poi"] = poi_cache.clear()

#     return results


if __name__ == "__main__":
    logger.info("Starting Geo API server")
    # Flush all deterministic caches on shutdown
    try:
        mcp.run(transport="stdio")
    finally:
        geocode_cache.flush()
        distance_cache.flush()

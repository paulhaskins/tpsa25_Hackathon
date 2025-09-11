"""
places.py - Office block sink detection via Google Places API.
"""

import networkx as nx
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import os
import json
import warnings
import hashlib
import time


def _get_cache_key(query: str, location: str, radius: int) -> str:
    """Generate a unique cache key for a search query."""
    cache_string = f"{query}_{location}_{radius}"
    return hashlib.md5(cache_string.encode()).hexdigest()


def _load_from_cache(cache_key: str) -> Optional[List[Dict[str, Any]]]:
    """Load search results from cache if they exist."""
    cache_file = Path("data/raw/places") / f"{cache_key}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache for {cache_key}: {e}")
    return None


def _save_to_cache(cache_key: str, results: List[Dict[str, Any]]) -> None:
    """Save search results to cache."""
    cache_file = Path("data/raw/places") / f"{cache_key}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(cache_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Cached {len(results)} results for query")
    except Exception as e:
        print(f"Error saving cache for {cache_key}: {e}")


def search_places(query: str, location: str, radius: int = 50000, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search Google Places with comprehensive caching.
    
    Args:
        query: Search query string
        location: Location string (e.g., "Dublin, Ireland")
        radius: Search radius in meters
        api_key: Google Places API key
    
    Returns:
        List of place results
    """
    if api_key is None:
        api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("Info: Google Places API key not configured, skipping search")
        return []
    
    # Generate cache key
    cache_key = _get_cache_key(query, location, radius)
    
    # Check cache first
    cached_results = _load_from_cache(cache_key)
    if cached_results is not None:
        print(f"Using cached results for: {query}")
        return cached_results
    
    try:
        import googlemaps
    except ImportError:
        warnings.warn("googlemaps library not available, skipping Google Places search")
        return []
    
    try:
        gmaps = googlemaps.Client(key=api_key)
        
        # Geocode the location first
        geocode_result = gmaps.geocode(location)
        if not geocode_result:
            print(f"Could not geocode location: {location}")
            return []
        
        location_coords = geocode_result[0]['geometry']['location']
        print(f"Searching Google Places: '{query}' around {location_coords}")
        
        all_results = []
        
        # Try text search first (returns richer results for large clusters)
        try:
            text_search_result = gmaps.places(
                query=query,
                location=location_coords,
                radius=radius
            )
            
            for place_data in text_search_result.get('results', []):
                place_info = _extract_place_info(place_data)
                all_results.append(place_info)
            
            # Handle pagination for text search
            next_page_token = text_search_result.get('next_page_token')
            while next_page_token:
                time.sleep(2)  # Required by Google Places API
                
                next_result = gmaps.places(
                    query=query,
                    location=location_coords,
                    radius=radius,
                    page_token=next_page_token
                )
                
                for place_data in next_result.get('results', []):
                    place_info = _extract_place_info(place_data)
                    all_results.append(place_info)
                
                next_page_token = next_result.get('next_page_token')
                
        except Exception as e:
            print(f"Text search failed for '{query}': {e}")
        
        # Remove duplicates based on place_id or name+location
        seen = set()
        unique_results = []
        for result in all_results:
            # Use place_id if available, otherwise use name+location
            if result.get('place_id'):
                key = result['place_id']
            else:
                key = (result.get('name', ''), round(result.get('lat', 0), 6), round(result.get('lon', 0), 6))
            
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        # Cache the results
        _save_to_cache(cache_key, unique_results)
        
        return unique_results
        
    except Exception as e:
        warnings.warn(f"Error with Google Places API search: {e}")
        return []


def _extract_place_info(place_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant information from Google Places API result."""
    return {
        'name': place_data.get('name', ''),
        'place_id': place_data.get('place_id', ''),
        'lat': place_data['geometry']['location']['lat'],
        'lon': place_data['geometry']['location']['lng'],
        'rating': place_data.get('rating', 0),
        'user_ratings_total': place_data.get('user_ratings_total', 0),
        'business_status': place_data.get('business_status', 'OPERATIONAL'),
        'types': place_data.get('types', []),
        'formatted_address': place_data.get('formatted_address', ''),
        'vicinity': place_data.get('vicinity', ''),
        'price_level': place_data.get('price_level', 0)
    }


def query_google_places_offices(place: str, api_key: Optional[str] = None) -> pd.DataFrame:
    """
    Query Google Places API for comprehensive office and business sink detection.
    
    Uses broader search queries and text search to find:
    - Office buildings
    - Business parks
    - Tech companies
    - Government offices
    - Hospitals
    - Universities
    
    Args:
        place: Place name to search (e.g., "Dublin, Ireland")
        api_key: Google Places API key (from GOOGLE_API_KEY env var if not provided)
    
    Returns:
        DataFrame with office/business place data
    """
    if api_key is None:
        api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("Info: Google Places API key not configured, skipping office detection (set GOOGLE_API_KEY env var to enable)")
        return pd.DataFrame()
    
    # Comprehensive search queries for different types of business sinks
    search_queries = [
        # Office buildings and corporate centers
        f"office building {place}",
        f"office block {place}",
        f"corporate headquarters {place}",
        f"business center {place}",
        f"commercial building {place}",
        f"office complex {place}",
        
        # Business parks and tech companies
        f"business park {place}",
        f"tech company {place}",
        f"technology company {place}",
        f"software company {place}",
        f"startup {place}",
        f"innovation center {place}",
        
        # Government and public offices
        f"government office {place}",
        f"public office {place}",
        f"council office {place}",
        f"ministry {place}",
        f"embassy {place}",
        f"consulate {place}",
        
        # Healthcare facilities
        f"hospital {place}",
        f"medical center {place}",
        f"clinic {place}",
        f"health center {place}",
        f"medical office {place}",
        
        # Educational institutions
        f"university {place}",
        f"college {place}",
        f"school {place}",
        f"research institute {place}",
        f"academic building {place}",
        
        # Financial and professional services
        f"bank {place}",
        f"financial services {place}",
        f"law firm {place}",
        f"accounting firm {place}",
        f"consulting firm {place}",
        f"insurance company {place}",
        
        # Industrial and manufacturing
        f"factory {place}",
        f"manufacturing {place}",
        f"industrial building {place}",
        f"warehouse {place}",
        f"distribution center {place}",
    ]
    
    all_places = []
    
    print(f"Searching Google Places for business sinks in {place}...")
    print(f"Using {len(search_queries)} different search queries")
    
    for i, query in enumerate(search_queries, 1):
        print(f"  [{i}/{len(search_queries)}] Searching: {query}")
        
        # Use the new search_places function with caching
        results = search_places(query, place, radius=50000, api_key=api_key)
        
        # Filter results to only include relevant business sinks
        for place_data in results:
            if _is_business_sink(place_data):
                # Convert to office format for compatibility
                office_info = _convert_to_office_format(place_data)
                all_places.append(office_info)
    
    # Remove duplicates based on place_id or name+location
    seen = set()
    unique_places = []
    for place_data in all_places:
        # Use place_id if available, otherwise use name+location
        if place_data.get('place_id'):
            key = place_data['place_id']
        else:
            key = (place_data.get('name', ''), round(place_data.get('lat', 0), 6), round(place_data.get('lon', 0), 6))
        
        if key not in seen:
            seen.add(key)
            unique_places.append(place_data)
    
    df = pd.DataFrame(unique_places)
    print(f"Found {len(df)} unique business sink locations")
    
    # Save to legacy cache format for backward compatibility
    legacy_cache_key = f"google_places_offices_{place.replace(' ', '_').replace(',', '')}"
    legacy_cache_file = Path("data/raw/places") / f"{legacy_cache_key}.json"
    legacy_cache_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(legacy_cache_file, 'w') as f:
            json.dump(df.to_dict('records'), f, indent=2)
        print(f"Saved results to legacy cache: {legacy_cache_file}")
    except Exception as e:
        print(f"Error saving legacy cache: {e}")
    
    return df


def _is_business_sink(place_data: Dict[str, Any]) -> bool:
    """Check if a place is likely a business sink (office, hospital, university, etc.)."""
    place_types = place_data.get('types', [])
    place_name = place_data.get('name', '').lower()
    
    # Business sink type indicators
    business_sink_types = [
        'establishment', 'point_of_interest', 'premise',
        'finance', 'insurance_agency', 'real_estate_agency',
        'lawyer', 'accountant', 'dentist', 'doctor',
        'travel_agency', 'car_dealer', 'car_repair',
        'hospital', 'school', 'university', 'college',
        'bank', 'atm', 'post_office', 'government',
        'embassy', 'consulate', 'courthouse', 'police',
        'fire_station', 'library', 'museum'
    ]
    
    # Name indicators that suggest business sinks
    business_sink_name_indicators = [
        'office', 'offices', 'building', 'tower', 'plaza', 'center', 'centre',
        'headquarters', 'hq', 'corporate', 'business', 'suite', 'floor',
        'ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation',
        'llc', 'group', 'associates', 'partners', 'consulting', 'services',
        'hospital', 'medical', 'clinic', 'health', 'university', 'college',
        'school', 'academy', 'institute', 'research', 'government', 'ministry',
        'embassy', 'consulate', 'bank', 'financial', 'insurance', 'law',
        'factory', 'manufacturing', 'warehouse', 'distribution'
    ]
    
    # Exclude non-business types
    exclude_types = [
        'restaurant', 'food', 'store', 'shopping_mall', 'supermarket',
        'gas_station', 'park', 'tourist_attraction', 'lodging', 'hotel',
        'bar', 'night_club', 'casino', 'amusement_park', 'zoo',
        'aquarium', 'art_gallery', 'movie_theater', 'stadium'
    ]
    
    # Check if any exclude types are present
    if any(exclude_type in place_types for exclude_type in exclude_types):
        return False
    
    # Check for business sink type indicators
    has_business_type = any(indicator in place_types for indicator in business_sink_types)
    
    # Check for business sink name indicators
    has_business_name = any(indicator in place_name for indicator in business_sink_name_indicators)
    
    # Must have either business type or business name indicators
    return has_business_type or has_business_name


def _convert_to_office_format(place_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert place data to office format for backward compatibility."""
    return {
        'name': place_data.get('name', ''),
        'place_type': _determine_place_type(place_data),
        'lat': place_data.get('lat', 0),
        'lon': place_data.get('lon', 0),
        'rating': place_data.get('rating', 0),
        'user_ratings_total': place_data.get('user_ratings_total', 0),
        'business_status': place_data.get('business_status', 'OPERATIONAL'),
        'types': place_data.get('types', []),
        'formatted_address': place_data.get('formatted_address', ''),
        'vicinity': place_data.get('vicinity', ''),
        'place_id': place_data.get('place_id', ''),
        'price_level': place_data.get('price_level', 0)
    }


def _determine_place_type(place_data: Dict[str, Any]) -> str:
    """Determine the primary place type based on types and name."""
    types = place_data.get('types', [])
    name = place_data.get('name', '').lower()
    
    # Priority order for type determination
    if any(t in types for t in ['hospital', 'doctor', 'dentist']):
        return 'hospital'
    elif any(t in types for t in ['university', 'school', 'college']):
        return 'university'
    elif any(t in types for t in ['bank', 'atm', 'finance']):
        return 'bank'
    elif any(t in types for t in ['government', 'embassy', 'consulate']):
        return 'government'
    elif any(t in types for t in ['lawyer', 'accountant']):
        return 'professional'
    elif any(t in types for t in ['factory', 'manufacturing']):
        return 'industrial'
    elif any(indicator in name for indicator in ['hospital', 'medical', 'clinic']):
        return 'hospital'
    elif any(indicator in name for indicator in ['university', 'college', 'school']):
        return 'university'
    elif any(indicator in name for indicator in ['bank', 'financial']):
        return 'bank'
    elif any(indicator in name for indicator in ['government', 'ministry', 'embassy']):
        return 'government'
    else:
        return 'office'


def _is_office_place(place_types: List[str], place_name: str) -> bool:
    """Legacy function - check if a place is likely an office based on types and name."""
    # Office-related type indicators
    office_type_indicators = [
        'establishment', 'point_of_interest', 'premise',
        'finance', 'insurance_agency', 'real_estate_agency',
        'lawyer', 'accountant', 'dentist', 'doctor',
        'travel_agency', 'car_dealer', 'car_repair'
    ]
    
    # Name indicators that suggest offices
    office_name_indicators = [
        'office', 'offices', 'building', 'tower', 'plaza', 'center', 'centre',
        'headquarters', 'hq', 'corporate', 'business', 'suite', 'floor',
        'ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation',
        'llc', 'group', 'associates', 'partners', 'consulting', 'services'
    ]
    
    # Exclude non-office types
    exclude_types = [
        'restaurant', 'food', 'store', 'shopping_mall', 'supermarket',
        'gas_station', 'hospital', 'school', 'university', 'church',
        'park', 'tourist_attraction', 'lodging', 'hotel'
    ]
    
    # Check if any exclude types are present
    if any(exclude_type in place_types for exclude_type in exclude_types):
        return False
    
    # Check for office type indicators
    has_office_type = any(indicator in place_types for indicator in office_type_indicators)
    
    # Check for office name indicators
    has_office_name = any(indicator in place_name for indicator in office_name_indicators)
    
    # Must have either office type or office name indicators
    return has_office_type or has_office_name


def _extract_office_info(place_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant information from Google Places API result."""
    return {
        'name': place_data.get('name', ''),
        'place_type': 'office',
        'lat': place_data['geometry']['location']['lat'],
        'lon': place_data['geometry']['location']['lng'],
        'rating': place_data.get('rating', 0),
        'user_ratings_total': place_data.get('user_ratings_total', 0),
        'business_status': place_data.get('business_status', 'OPERATIONAL'),
        'types': place_data.get('types', []),
        'formatted_address': place_data.get('formatted_address', ''),
        'vicinity': place_data.get('vicinity', '')
    }


def map_offices_to_sink_nodes(offices_df: pd.DataFrame, G: nx.Graph, max_distance: float = 200.0) -> Dict[int, Dict[str, Any]]:
    """
    Map office locations to sink nodes in the graph.
    
    Args:
        offices_df: DataFrame with office data
        G: Road graph
        max_distance: Maximum distance in meters to consider a match
    
    Returns:
        Dictionary mapping node_id -> sink node info
    """
    if offices_df.empty:
        return {}
    
    # Get node coordinates
    node_coords = {}
    for node, data in G.nodes(data=True):
        if data.get('x') is not None and data.get('y') is not None:
            node_coords[node] = (data['x'], data['y'])
    
    if not node_coords:
        return {}
    
    # Convert to arrays for efficient distance calculation
    node_ids = list(node_coords.keys())
    node_lons = np.array([node_coords[n][0] for n in node_ids])
    node_lats = np.array([node_coords[n][1] for n in node_ids])
    
    sink_nodes = {}
    
    for _, office in offices_df.iterrows():
        if pd.isna(office.get('lon')) or pd.isna(office.get('lat')):
            continue
        
        # Calculate distances to all nodes
        distances = np.sqrt(
            (node_lons - office['lon'])**2 + (node_lats - office['lat'])**2
        ) * 111000  # Rough conversion to meters
        
        # Find nearest node
        nearest_idx = np.argmin(distances)
        nearest_distance = distances[nearest_idx]
        
        if nearest_distance <= max_distance:
            nearest_node = node_ids[nearest_idx]
            
            # Estimate person capacity based on office characteristics
            person_capacity = _estimate_office_capacity(office)
            
            # Create sink node info
            sink_nodes[nearest_node] = {
                'type': 'sink',
                'place_type': 'office',
                'office_name': office.get('name', 'Unknown Office'),
                'office_type': office.get('place_type', 'office'),
                'person_capacity': person_capacity,
                'population_capacity': person_capacity,  # Alias for compatibility
                'google_place_type': office.get('place_type', 'office'),
                'rating': office.get('rating', 0),
                'business_status': office.get('business_status', 'OPERATIONAL'),
                'distance_to_office': nearest_distance,
                'office_lat': office['lat'],
                'office_lon': office['lon']
            }
    
    return sink_nodes


def _estimate_office_capacity(office: Dict[str, Any]) -> int:
    """Estimate person capacity for a business sink based on type and available information."""
    place_type = office.get('place_type', 'office')
    name = office.get('name', '').lower()
    
    # Get capacity estimate using tier-based classification
    capacity_estimate = _classify_business_capacity_tier(office)
    
    return capacity_estimate


def _classify_business_capacity_tier(office: Dict[str, Any]) -> int:
    """
    Classify business capacity into tiers based on type, reviews, and other indicators.
    
    Tiers:
    - Low: 1-10 people
    - Medium: 11-50 people  
    - High: 51-250 people
    - Massive: 250+ people
    """
    place_type = office.get('place_type', 'office')
    name = office.get('name', '').lower()
    rating = office.get('rating', 0)
    review_count = office.get('user_ratings_total', 0)
    business_status = office.get('business_status', 'OPERATIONAL')
    
    # Base capacity by business type
    type_base_capacities = {
        # Healthcare
        'hospital': {'base': 500, 'tier': 'high'},
        'clinic': {'base': 20, 'tier': 'low'},
        'medical': {'base': 15, 'tier': 'low'},
        
        # Education
        'university': {'base': 2000, 'tier': 'massive'},
        'college': {'base': 800, 'tier': 'high'},
        'school': {'base': 200, 'tier': 'high'},
        
        # Financial
        'bank': {'base': 100, 'tier': 'medium'},
        'financial': {'base': 80, 'tier': 'medium'},
        
        # Government
        'government': {'base': 300, 'tier': 'high'},
        'embassy': {'base': 50, 'tier': 'medium'},
        'consulate': {'base': 30, 'tier': 'low'},
        
        # Professional services
        'professional': {'base': 25, 'tier': 'low'},
        'law': {'base': 30, 'tier': 'low'},
        'accounting': {'base': 20, 'tier': 'low'},
        'consulting': {'base': 40, 'tier': 'low'},
        
        # Industrial
        'industrial': {'base': 200, 'tier': 'high'},
        'factory': {'base': 300, 'tier': 'high'},
        'warehouse': {'base': 150, 'tier': 'high'},
        'manufacturing': {'base': 250, 'tier': 'high'},
        
        # Default office
        'office': {'base': 50, 'tier': 'medium'}
    }
    
    # Get base capacity and tier
    type_info = type_base_capacities.get(place_type, {'base': 50, 'tier': 'medium'})
    base_capacity = type_info['base']
    base_tier = type_info['tier']
    
    # Tier multipliers based on review count (proxy for size/visibility)
    review_multiplier = 1.0
    if review_count >= 1000:
        review_multiplier = 2.5  # Very large/well-known
    elif review_count >= 500:
        review_multiplier = 2.0  # Large
    elif review_count >= 200:
        review_multiplier = 1.5  # Medium-large
    elif review_count >= 100:
        review_multiplier = 1.2  # Medium
    elif review_count >= 50:
        review_multiplier = 1.1  # Small-medium
    elif review_count >= 20:
        review_multiplier = 1.0  # Small
    else:
        review_multiplier = 0.8  # Very small/unknown
    
    # Name-based adjustments
    name_multiplier = 1.0
    if any(indicator in name for indicator in ['headquarters', 'hq', 'corporate', 'tower', 'building', 'main', 'central']):
        name_multiplier = 2.0  # Major facility
    elif any(indicator in name for indicator in ['center', 'centre', 'plaza', 'group', 'complex', 'campus']):
        name_multiplier = 1.5  # Large facility
    elif any(indicator in name for indicator in ['branch', 'satellite', 'small', 'mini', 'local']):
        name_multiplier = 0.7  # Small facility
    
    # Rating-based adjustments (higher rating might indicate better/more established)
    rating_multiplier = 1.0
    if rating >= 4.5:
        rating_multiplier = 1.3
    elif rating >= 4.0:
        rating_multiplier = 1.1
    elif rating >= 3.5:
        rating_multiplier = 1.0
    else:
        rating_multiplier = 0.9
    
    # Calculate final capacity
    final_capacity = int(base_capacity * review_multiplier * name_multiplier * rating_multiplier)
    
    # Apply tier-based constraints
    tier_constraints = {
        'low': (1, 10),
        'medium': (11, 50),
        'high': (51, 250),
        'massive': (251, 5000)
    }
    
    min_cap, max_cap = tier_constraints.get(base_tier, (1, 1000))
    
    # Special overrides for specific types
    if place_type == 'hospital':
        min_cap, max_cap = (50, 2000)
    elif place_type == 'university':
        min_cap, max_cap = (100, 5000)
    elif place_type == 'government':
        min_cap, max_cap = (20, 1000)
    
    # Clamp to tier constraints
    final_capacity = max(min_cap, min(max_cap, final_capacity))
    
    # Add capacity estimate to office data
    office['capacity_estimate'] = final_capacity
    office['capacity_tier'] = base_tier
    office['capacity_factors'] = {
        'base_capacity': base_capacity,
        'review_multiplier': review_multiplier,
        'name_multiplier': name_multiplier,
        'rating_multiplier': rating_multiplier,
        'review_count': review_count,
        'rating': rating
    }
    
    return final_capacity


def create_sink_nodes_from_offices(G: nx.Graph, offices_df: pd.DataFrame) -> nx.Graph:
    """
    Create sink nodes from office data at their exact GPS coordinates and connect them to the nearest road.
    
    Args:
        G: Road graph
        offices_df: DataFrame with office data
    
    Returns:
        Graph with sink nodes added at exact GPS coordinates
    """
    G = G.copy()
    
    if offices_df.empty:
        return G
    
    # Get existing node coordinates for finding nearest roads
    node_coords = {}
    for node, data in G.nodes(data=True):
        if data.get('x') is not None and data.get('y') is not None:
            node_coords[node] = (data['x'], data['y'])
    
    if not node_coords:
        print("Warning: No existing nodes with coordinates found")
        return G
    
    # Convert to arrays for efficient distance calculation
    node_ids = list(node_coords.keys())
    node_lons = np.array([node_coords[n][0] for n in node_ids])
    node_lats = np.array([node_coords[n][1] for n in node_ids])
    
    created_sinks = 0
    connected_sinks = 0
    
    for idx, office in offices_df.iterrows():
        if pd.isna(office.get('lon')) or pd.isna(office.get('lat')):
            continue
        
        # Create a unique node ID for this business sink
        business_node_id = f"business_sink_{idx}_{office.get('place_id', '')}"
        
        # Estimate person capacity based on office characteristics using tier-based classification
        person_capacity = _estimate_office_capacity(office)
        
        # Create the business sink node at its exact GPS coordinates
        G.add_node(business_node_id, 
                  x=office['lon'],  # Longitude
                  y=office['lat'],  # Latitude
                  type='sink',
                  place_type='office',
                  office_name=office.get('name', 'Unknown Office'),
                  office_type=office.get('place_type', 'office'),
                  person_capacity=person_capacity,
                  population_capacity=office.get('capacity_estimate', person_capacity),  # Use tier-based estimate
                  google_place_type=office.get('place_type', 'office'),
                  rating=office.get('rating', 0),
                  business_status=office.get('business_status', 'OPERATIONAL'),
                  office_lat=office['lat'],
                  office_lon=office['lon'],
                  category='Business',
                  is_sink=True,
                  is_business_sink=True,
                  capacity_estimate=office.get('capacity_estimate', person_capacity),
                  capacity_tier=office.get('capacity_tier', 'medium'),
                  capacity_factors=office.get('capacity_factors', {}))
        
        created_sinks += 1
        
        # Find the nearest road node to connect to
        distances = np.sqrt(
            (node_lons - office['lon'])**2 + (node_lats - office['lat'])**2
        ) * 111000  # Rough conversion to meters
        
        # Find nearest node
        nearest_idx = np.argmin(distances)
        nearest_distance = distances[nearest_idx]
        nearest_node = node_ids[nearest_idx]
        
        # Create sophisticated access road to the business
        business_coords = (office['lon'], office['lat'])
        nearest_coords = (node_coords[nearest_node][0], node_coords[nearest_node][1])
        
        G = create_business_access_road(G, business_node_id, business_coords, 
                                      nearest_node, nearest_coords)
        
        connected_sinks += 1
    
    print(f"Created {created_sinks} business sink nodes at exact GPS coordinates")
    print(f"Connected {connected_sinks} business sinks to nearest roads")
    
    return G


def create_business_access_road(G: nx.Graph, business_node_id: str, business_coords: Tuple[float, float], 
                               nearest_node: int, nearest_coords: Tuple[float, float], 
                               max_direct_distance: float = 100.0) -> nx.Graph:
    """
    Create a more realistic access road for business sinks.
    
    If the distance is too long, create intermediate nodes to simulate a proper driveway/access road.
    
    Args:
        G: Road graph
        business_node_id: ID of the business sink node
        business_coords: (lon, lat) coordinates of the business
        nearest_node: ID of the nearest road node
        nearest_coords: (lon, lat) coordinates of the nearest road node
        max_direct_distance: Maximum distance (meters) for direct connection
    
    Returns:
        Updated graph with access road
    """
    business_lon, business_lat = business_coords
    road_lon, road_lat = nearest_coords
    
    # Calculate distance
    distance = np.sqrt(
        (business_lon - road_lon)**2 + (business_lat - road_lat)**2
    ) * 111000  # Rough conversion to meters
    
    if distance <= max_direct_distance:
        # Direct connection for short distances
        G.add_edge(business_node_id, nearest_node, 
                  length=distance,
                  lanes=1,
                  highway='service',
                  name=f"Direct access to business",
                  is_business_access=True,
                  access_type='business_driveway')
        
        G.add_edge(nearest_node, business_node_id,
                  length=distance, 
                  lanes=1,
                  highway='service',
                  name=f"Direct access from business",
                  is_business_access=True,
                  access_type='business_driveway')
    else:
        # Create intermediate nodes for longer access roads
        num_intermediate = min(int(distance / 50), 3)  # Max 3 intermediate nodes, every ~50m
        
        prev_node = nearest_node
        prev_coords = nearest_coords
        
        for i in range(num_intermediate):
            # Calculate intermediate point
            t = (i + 1) / (num_intermediate + 1)
            intermediate_lon = road_lon + t * (business_lon - road_lon)
            intermediate_lat = road_lat + t * (business_lat - road_lat)
            
            # Create intermediate node
            intermediate_id = f"{business_node_id}_access_{i+1}"
            G.add_node(intermediate_id,
                      x=intermediate_lon,
                      y=intermediate_lat,
                      type='access_point',
                      is_business_access=True)
            
            # Connect to previous node
            segment_distance = np.sqrt(
                (intermediate_lon - prev_coords[0])**2 + (intermediate_lat - prev_coords[1])**2
            ) * 111000
            
            G.add_edge(prev_node, intermediate_id,
                      length=segment_distance,
                      lanes=1,
                      highway='service',
                      name=f"Access road segment {i+1}",
                      is_business_access=True,
                      access_type='business_driveway')
            
            G.add_edge(intermediate_id, prev_node,
                      length=segment_distance,
                      lanes=1,
                      highway='service',
                      name=f"Access road segment {i+1} (reverse)",
                      is_business_access=True,
                      access_type='business_driveway')
            
            prev_node = intermediate_id
            prev_coords = (intermediate_lon, intermediate_lat)
        
        # Final connection to business
        final_distance = np.sqrt(
            (business_lon - prev_coords[0])**2 + (business_lat - prev_coords[1])**2
        ) * 111000
        
        G.add_edge(prev_node, business_node_id,
                  length=final_distance,
                  lanes=1,
                  highway='service',
                  name=f"Final access to business",
                  is_business_access=True,
                  access_type='business_driveway')
        
        G.add_edge(business_node_id, prev_node,
                  length=final_distance,
                  lanes=1,
                  highway='service',
                  name=f"Final access from business",
                  is_business_access=True,
                  access_type='business_driveway')
    
    return G


def detect_office_sinks(G: nx.Graph, place: str, api_key: Optional[str] = None) -> nx.Graph:
    """
    Detect office sinks using Google Places API and integrate them into the graph.
    
    Args:
        G: Road graph
        place: Place name for Google Places search
        api_key: Google Places API key (optional)
    
    Returns:
        Graph with office sink nodes added
    """
    # Query Google Places for offices
    offices_df = query_google_places_offices(place, api_key)
    
    if offices_df.empty:
        print("No office data found, skipping sink detection")
        return G
    
    # Filter offices to 18km radius from Dublin center if place is Dublin
    if "Dublin" in place:
        offices_df = filter_offices_to_18km_radius(offices_df)
        print(f"Filtered to {len(offices_df)} offices within 18km of Dublin center")
    
    # Create sink nodes from office data
    G_with_sinks = create_sink_nodes_from_offices(G, offices_df)
    
    return G_with_sinks


def filter_offices_to_18km_radius(offices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter offices DataFrame to only include those within 18km of Dublin center.
    
    Args:
        offices_df: DataFrame with office data including lat/lon columns
    
    Returns:
        Filtered DataFrame with only offices within 18km radius
    """
    if offices_df.empty:
        return offices_df
    
    # Dublin city center coordinates (Spire of Dublin)
    dublin_center_lat = 53.3498
    dublin_center_lon = -6.2603
    radius_km = 18
    
    # Calculate distances from Dublin center
    distances = []
    for _, row in offices_df.iterrows():
        lat = row.get('lat')
        lon = row.get('lng')  # Google Places uses 'lng' for longitude
        
        if pd.isna(lat) or pd.isna(lon):
            distances.append(float('inf'))
            continue
            
        # Calculate distance in km
        distance = np.sqrt(
            (lat - dublin_center_lat)**2 + 
            (lon - dublin_center_lon)**2
        ) * 111.0  # Convert to km
        
        distances.append(distance)
    
    # Filter to offices within 18km radius
    mask = np.array(distances) <= radius_km
    filtered_df = offices_df.loc[mask].copy()
    
    return filtered_df


__all__ = [
    "search_places",
    "query_google_places_offices",
    "map_offices_to_sink_nodes",
    "create_sink_nodes_from_offices",
    "create_business_access_road",
    "detect_office_sinks",
    "filter_offices_to_18km_radius",
    "_is_business_sink",
    "_convert_to_office_format",
    "_determine_place_type",
    "_is_office_place",
    "_extract_office_info",
    "_extract_place_info",
    "_estimate_office_capacity",
    "_get_cache_key",
    "_load_from_cache",
    "_save_to_cache",
]

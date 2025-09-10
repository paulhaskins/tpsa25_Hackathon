"""
categories.py - Classify nodes and supernodes into functional categories.
"""

import networkx as nx
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path
import os
import warnings
import json


def classify_poi_category(tags: Dict[str, str]) -> str:
    """
    Classify a node/POI based on OSM tags into categories.

    Args:
        tags (dict): OSM tags.

    Returns:
        str: Category ("Residential", "Business", "Transport", "School", "Hospital", "Other")
    """
    if not tags:
        return "Other"
    
    # Convert tags to lowercase for case-insensitive matching
    tags_lower = {k.lower(): str(v).lower() for k, v in tags.items()}
    
    # Check for residential indicators
    residential_indicators = ['residential', 'house', 'apartment', 'housing', 'residential']
    if any(tag in tags_lower.get('landuse', '') for tag in residential_indicators):
        return "Residential"
    if any(tag in tags_lower.get('amenity', '') for tag in ['house', 'apartment']):
        return "Residential"
    
    # Check for business/commercial indicators
    business_indicators = ['commercial', 'retail', 'office', 'industrial', 'business']
    if any(tag in tags_lower.get('landuse', '') for tag in business_indicators):
        return "Business"
    if any(tag in tags_lower.get('amenity', '') for tag in ['shop', 'market', 'bank', 'restaurant', 'cafe']):
        return "Business"
    if 'shop' in tags_lower and tags_lower['shop']:  # Any shop type
        return "Business"
    if 'office' in tags_lower and tags_lower['office']:  # Any office type
        return "Business"
    
    # Check for transport indicators
    transport_indicators = ['station', 'stop', 'terminal', 'depot']
    if any(tag in tags_lower.get('amenity', '') for tag in ['bus_station', 'taxi', 'fuel']):
        return "Transport"
    if any(tag in tags_lower.get('public_transport', '') for tag in ['station', 'stop']):
        return "Transport"
    if any(tag in tags_lower.get('railway', '') for tag in ['station', 'halt', 'tram_stop']):
        return "Transport"
    if any(tag in tags_lower.get('highway', '') for tag in ['bus_stop']):
        return "Transport"
    
    # Check for school indicators
    school_indicators = ['school', 'university', 'college', 'kindergarten', 'education']
    if any(tag in tags_lower.get('amenity', '') for tag in school_indicators):
        return "School"
    if any(tag in tags_lower.get('landuse', '') for tag in ['education']):
        return "School"
    
    # Check for hospital/medical indicators
    medical_indicators = ['hospital', 'clinic', 'medical', 'health', 'pharmacy']
    if any(tag in tags_lower.get('amenity', '') for tag in medical_indicators):
        return "Hospital"
    if any(tag in tags_lower.get('landuse', '') for tag in ['health']):
        return "Hospital"
    
    # Default to Other if no specific category matches
    return "Other"


def assign_categories_to_nodes(G: nx.Graph) -> nx.Graph:
    """
    Annotate nodes/supernodes in the graph with 'category' attribute.

    Args:
        G (nx.Graph): Road graph.

    Returns:
        nx.Graph: Graph with category annotations.
    """
    for node, data in G.nodes(data=True):
        # Extract OSM tags from node data
        tags = {}
        for key, value in data.items():
            # OSM tags are typically stored as direct attributes
            if key not in ['x', 'y', 'lat', 'lon', 'is_supernode', 'members', 'type', 'population_capacity']:
                tags[key] = value
        
        # Classify the node
        category = classify_poi_category(tags)
        G.nodes[node]['category'] = category
    
    return G


def query_osm_pois(place: str, poi_types: Optional[Dict[str, List[str]]] = None) -> pd.DataFrame:
    """
    Query OSM POIs for a given place using OSMnx.
    
    Args:
        place: Place name for OSMnx query
        poi_types: Dictionary of POI types to query (default: comprehensive set)
    
    Returns:
        DataFrame with POI data including geometry and tags
    """
    try:
        import osmnx as ox
    except ImportError:
        warnings.warn("OSMnx not available, skipping POI querying")
        return pd.DataFrame()
    
    # Suppress GeoPandas fragmentation warnings for this function
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
        
        if poi_types is None:
            poi_types = {
                'amenity': ['school', 'hospital', 'university', 'college', 'kindergarten', 
                           'clinic', 'pharmacy', 'bank', 'restaurant', 'cafe', 'fuel',
                           'bus_station', 'taxi', 'police', 'fire_station'],
                'shop': ['*'],  # All shop types
                'office': ['*'],  # All office types
                'landuse': ['commercial', 'retail', 'industrial', 'education', 'health'],
                'leisure': ['park', 'sports_centre', 'swimming_pool', 'golf_course'],
                'tourism': ['hotel', 'museum', 'attraction', 'information'],
                'railway': ['station', 'halt', 'tram_stop'],
                'public_transport': ['station', 'stop']
            }
        
        all_pois = []
        
        for tag_type, values in poi_types.items():
            for value in values:
                try:
                    if value == '*':
                        # Query all values for this tag type
                        pois = ox.features_from_place(place, tags={tag_type: True})
                    else:
                        # Query specific value
                        pois = ox.features_from_place(place, tags={tag_type: value})
                    
                    if not pois.empty:
                        # Add tag information
                        pois['poi_type'] = tag_type
                        pois['poi_value'] = value
                        all_pois.append(pois)
                        
                except Exception as e:
                    # Only warn for unexpected errors, not for "no matching features"
                    if "No matching features" not in str(e):
                        warnings.warn(f"Error querying {tag_type}={value} for {place}: {e}")
                    continue
        
        if not all_pois:
            return pd.DataFrame()
        
        # Combine all POIs
        combined_pois = pd.concat(all_pois, ignore_index=True)
        
        # Extract coordinates
        if 'geometry' in combined_pois.columns:
            combined_pois['lon'] = combined_pois.geometry.apply(lambda x: x.centroid.x if hasattr(x, 'centroid') else None)
            combined_pois['lat'] = combined_pois.geometry.apply(lambda x: x.centroid.y if hasattr(x, 'centroid') else None)
        
        return combined_pois


def map_pois_to_nodes(pois_df: pd.DataFrame, G: nx.Graph, max_distance: float = 100.0) -> Dict[int, str]:
    """
    Map POIs to the nearest nodes in the graph.
    
    Args:
        pois_df: DataFrame with POI data including lat/lon
        G: Road graph
        max_distance: Maximum distance in meters to consider a match
    
    Returns:
        Dictionary mapping node_id -> category
    """
    if pois_df.empty:
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
    
    node_categories = {}
    
    for _, poi in pois_df.iterrows():
        if pd.isna(poi.get('lon')) or pd.isna(poi.get('lat')):
            continue
        
        # Calculate distances to all nodes
        distances = np.sqrt(
            (node_lons - poi['lon'])**2 + (node_lats - poi['lat'])**2
        ) * 111000  # Rough conversion to meters (1 degree ≈ 111km)
        
        # Find nearest node
        nearest_idx = np.argmin(distances)
        nearest_distance = distances[nearest_idx]
        
        if nearest_distance <= max_distance:
            nearest_node = node_ids[nearest_idx]
            
            # Classify POI
            poi_tags = {poi.get('poi_type', ''): poi.get('poi_value', '')}
            category = classify_poi_category(poi_tags)
            
            # Only update if we have a more specific category than "Other"
            if category != "Other" or nearest_node not in node_categories:
                node_categories[nearest_node] = category
                
                # Store additional POI information for business nodes
                if category == "Business" and nearest_node in G.nodes:
                    # Store business type information
                    poi_type = poi.get('poi_type', '')
                    poi_value = poi.get('poi_value', '')
                    if poi_type and poi_value:
                        G.nodes[nearest_node][poi_type] = poi_value
    
    return node_categories


def query_google_places(place: str, api_key: Optional[str] = None) -> pd.DataFrame:
    """
    Query Google Places API for comprehensive business/transport locations with caching.
    
    Args:
        place: Place name to search
        api_key: Google Places API key (from GOOGLE_API_KEY env var if not provided)
    
    Returns:
        DataFrame with place data
    """
    if api_key is None:
        api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        # This is expected for demo purposes, so use info level instead of warning
        print("Info: Google Places API key not configured, skipping Google Places query (set GOOGLE_API_KEY env var to enable)")
        return pd.DataFrame()
    
    try:
        import googlemaps
    except ImportError:
        warnings.warn("googlemaps library not available, skipping Google Places query")
        return pd.DataFrame()
    
    # Check cache first
    cache_key = f"google_places_{place.replace(' ', '_').replace(',', '')}"
    cache_file = Path("cache") / f"{cache_key}.json"
    
    if cache_file.exists():
        print(f"Loading cached Google Places data for {place}")
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            return pd.DataFrame(cached_data)
        except Exception as e:
            print(f"Error loading cache: {e}")
    
    try:
        gmaps = googlemaps.Client(key=api_key)
        
        # Geocode the place first
        geocode_result = gmaps.geocode(place)
        if not geocode_result:
            return pd.DataFrame()
        
        location = geocode_result[0]['geometry']['location']
        print(f"Searching Google Places around {location} for {place}")
        
        # Comprehensive search categories
        place_types = [
            # Business categories
            'restaurant', 'food', 'store', 'shopping_mall', 'supermarket', 'grocery_or_supermarket',
            'clothing_store', 'electronics_store', 'furniture_store', 'hardware_store',
            'pharmacy', 'gas_station', 'bank', 'atm', 'post_office',
            'beauty_salon', 'hair_care', 'spa', 'gym', 'fitness_center',
            'car_dealer', 'car_repair', 'car_wash', 'parking',
            
            # Healthcare
            'hospital', 'doctor', 'dentist', 'veterinary_care', 'pharmacy',
            
            # Education
            'school', 'university', 'library',
            
            # Transport
            'airport', 'train_station', 'bus_station', 'subway_station', 'taxi_stand',
            
            # Entertainment & Tourism
            'tourist_attraction', 'museum', 'movie_theater', 'night_club', 'bar',
            'lodging', 'hotel', 'campground',
            
            # Government & Services
            'government', 'police', 'fire_station', 'courthouse', 'embassy',
            
            # Religious
            'church', 'mosque', 'synagogue', 'hindu_temple', 'place_of_worship'
        ]
        
        all_places = []
        
        for place_type in place_types:
            try:
                print(f"  Searching for {place_type}...")
                
                # Search for places of this type
                places_result = gmaps.places_nearby(
                    location=location,
                    radius=50000,  # 50km radius
                    type=place_type
                )
                
                # Process results
                for place_data in places_result.get('results', []):
                    place_info = {
                        'name': place_data.get('name', ''),
                        'place_type': place_type,
                        'lat': place_data['geometry']['location']['lat'],
                        'lon': place_data['geometry']['location']['lng'],
                        'rating': place_data.get('rating', 0),
                        'user_ratings_total': place_data.get('user_ratings_total', 0),
                        'business_status': place_data.get('business_status', 'OPERATIONAL'),
                        'types': place_data.get('types', [])
                    }
                    all_places.append(place_info)
                
                # Handle pagination for more results
                next_page_token = places_result.get('next_page_token')
                while next_page_token:
                    try:
                        # Wait a bit for the token to become valid
                        import time
                        time.sleep(2)
                        
                        next_result = gmaps.places_nearby(
                            location=location,
                            radius=50000,
                            type=place_type,
                            page_token=next_page_token
                        )
                        
                        for place_data in next_result.get('results', []):
                            place_info = {
                                'name': place_data.get('name', ''),
                                'place_type': place_type,
                                'lat': place_data['geometry']['location']['lat'],
                                'lon': place_data['geometry']['location']['lng'],
                                'rating': place_data.get('rating', 0),
                                'user_ratings_total': place_data.get('user_ratings_total', 0),
                                'business_status': place_data.get('business_status', 'OPERATIONAL'),
                                'types': place_data.get('types', [])
                            }
                            all_places.append(place_info)
                        
                        next_page_token = next_result.get('next_page_token')
                        
                    except Exception as e:
                        print(f"    Error with pagination for {place_type}: {e}")
                        break
                        
            except Exception as e:
                print(f"  Error querying Google Places for {place_type}: {e}")
                continue
        
        # Also do a general text search for more comprehensive results
        try:
            print("  Doing general text search...")
            text_search_result = gmaps.places(
                query=f"businesses in {place}",
                location=location,
                radius=50000
            )
            
            for place_data in text_search_result.get('results', []):
                place_info = {
                    'name': place_data.get('name', ''),
                    'place_type': 'general_business',
                    'lat': place_data['geometry']['location']['lat'],
                    'lon': place_data['geometry']['location']['lng'],
                    'rating': place_data.get('rating', 0),
                    'user_ratings_total': place_data.get('user_ratings_total', 0),
                    'business_status': place_data.get('business_status', 'OPERATIONAL'),
                    'types': place_data.get('types', [])
                }
                all_places.append(place_info)
                
        except Exception as e:
            print(f"  Error with text search: {e}")
        
        # Remove duplicates based on name and location
        seen = set()
        unique_places = []
        for place in all_places:
            key = (place['name'], round(place['lat'], 6), round(place['lon'], 6))
            if key not in seen:
                seen.add(key)
                unique_places.append(place)
        
        df = pd.DataFrame(unique_places)
        print(f"Found {len(df)} unique Google Places")
        
        # Cache the results
        cache_file.parent.mkdir(exist_ok=True)
        with open(cache_file, 'w') as f:
            json.dump(df.to_dict('records'), f, indent=2)
        print(f"Cached results to {cache_file}")
        
        return df
        
    except Exception as e:
        warnings.warn(f"Error with Google Places API: {e}")
        return pd.DataFrame()


def map_google_places_to_nodes(places_df: pd.DataFrame, G: nx.Graph, max_distance: float = 200.0) -> Dict[int, str]:
    """
    Map Google Places to the nearest nodes in the graph.
    
    Args:
        places_df: DataFrame with Google Places data
        G: Road graph
        max_distance: Maximum distance in meters to consider a match
    
    Returns:
        Dictionary mapping node_id -> category
    """
    if places_df.empty:
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
    
    node_categories = {}
    
    for _, place in places_df.iterrows():
        if pd.isna(place.get('lon')) or pd.isna(place.get('lat')):
            continue
        
        # Calculate distances to all nodes
        distances = np.sqrt(
            (node_lons - place['lon'])**2 + (node_lats - place['lat'])**2
        ) * 111000  # Rough conversion to meters
        
        # Find nearest node
        nearest_idx = np.argmin(distances)
        nearest_distance = distances[nearest_idx]
        
        if nearest_distance <= max_distance:
            nearest_node = node_ids[nearest_idx]
            
            # Map Google place type to our categories
            place_type = place.get('place_type', '')
            category = map_google_place_type_to_category(place_type)
            
            # Only update if we have a more specific category than "Other"
            if category != "Other" or nearest_node not in node_categories:
                node_categories[nearest_node] = category
                
                # Store additional business information for business nodes
                if category == "Business" and nearest_node in G.nodes:
                    # Store Google Places information
                    place_name = place.get('name', '')
                    if place_name:
                        G.nodes[nearest_node]['name'] = place_name
                    if place_type:
                        G.nodes[nearest_node]['google_place_type'] = place_type
    
    return node_categories


def map_google_place_type_to_category(place_type: str) -> str:
    """Map Google Places API types to our categories."""
    mapping = {
        'shopping_mall': 'Business',
        'airport': 'Transport',
        'train_station': 'Transport',
        'bus_station': 'Transport',
        'hospital': 'Hospital',
        'university': 'School',
        'school': 'School',
        'government': 'Business',
        'bank': 'Business',
        'restaurant': 'Business',
        'lodging': 'Business',
        'tourist_attraction': 'Business'
    }
    return mapping.get(place_type, 'Other')


def detect_business_heuristics(G: nx.Graph, place: str) -> Dict[int, str]:
    """
    Fallback heuristics to detect business areas when POI data is unavailable.
    
    Args:
        G: Road graph
        place: Place name for context
    
    Returns:
        Dictionary mapping node_id -> category
    """
    node_categories = {}
    
    # Get graph center
    if not G.nodes:
        return node_categories
    
    # Calculate graph center
    lons = [data.get('x', 0) for _, data in G.nodes(data=True) if data.get('x') is not None]
    lats = [data.get('y', 0) for _, data in G.nodes(data=True) if data.get('y') is not None]
    
    if not lons or not lats:
        return node_categories
    
    center_lon = np.mean(lons)
    center_lat = np.mean(lats)
    
    # Find nodes near city center with high connectivity
    for node, data in G.nodes(data=True):
        if data.get('x') is None or data.get('y') is None:
            continue
        
        # Distance from center
        distance_from_center = np.sqrt(
            (data['x'] - center_lon)**2 + (data['y'] - center_lat)**2
        ) * 111000  # Convert to meters
        
        # Node degree (connectivity)
        degree = G.degree(node)
        
        # Heuristic: high-degree nodes near city center are likely business areas
        if distance_from_center < 5000 and degree >= 4:  # Within 5km of center, 4+ connections
            node_categories[node] = 'Business'
        elif distance_from_center < 2000 and degree >= 3:  # Within 2km of center, 3+ connections
            node_categories[node] = 'Business'
    
    return node_categories


def assign_categories_enhanced(G: nx.Graph, place: str, use_osm: bool = True, 
                             use_google: bool = True, use_heuristics: bool = True) -> nx.Graph:
    """
    Enhanced category assignment using multiple data sources.
    
    Args:
        G: Road graph
        place: Place name for POI queries
        use_osm: Whether to use OSM POI data
        use_google: Whether to use Google Places API
        use_heuristics: Whether to use fallback heuristics
    
    Returns:
        Graph with enhanced category annotations
    """
    G = G.copy()
    
    # Start with basic category assignment
    G = assign_categories_to_nodes(G)
    
    # Collect all category mappings
    all_categories = {}
    
    # 1. OSM POI integration
    if use_osm:
        try:
            print(f"Querying OSM POIs for {place}...")
            pois_df = query_osm_pois(place)
            if not pois_df.empty:
                osm_categories = map_pois_to_nodes(pois_df, G)
                all_categories.update(osm_categories)
                print(f"  Mapped {len(osm_categories)} OSM POIs to nodes")
        except Exception as e:
            warnings.warn(f"Error in OSM POI integration: {e}")
    
    # 2. Google Places API integration
    if use_google:
        try:
            print(f"Querying Google Places for {place}...")
            places_df = query_google_places(place)
            if not places_df.empty:
                google_categories = map_google_places_to_nodes(places_df, G)
                all_categories.update(google_categories)
                print(f"  Mapped {len(google_categories)} Google Places to nodes")
        except Exception as e:
            warnings.warn(f"Error in Google Places integration: {e}")
    
    # 3. Fallback heuristics
    if use_heuristics:
        try:
            print(f"Applying business detection heuristics for {place}...")
            heuristic_categories = detect_business_heuristics(G, place)
            # Only add if not already categorized
            for node, category in heuristic_categories.items():
                if node not in all_categories:
                    all_categories[node] = category
            print(f"  Applied heuristics to {len(heuristic_categories)} nodes")
        except Exception as e:
            warnings.warn(f"Error in heuristic detection: {e}")
    
    # Apply all category mappings
    for node, category in all_categories.items():
        if node in G.nodes:
            G.nodes[node]['category'] = category
    
    # Print summary
    category_counts = {}
    for _, data in G.nodes(data=True):
        category = data.get('category', 'Other')
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print(f"Category assignment summary:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count} nodes")
    
    return G


__all__ = [
    "classify_poi_category",
    "assign_categories_to_nodes",
    "query_osm_pois",
    "map_pois_to_nodes",
    "query_google_places",
    "map_google_places_to_nodes",
    "map_google_place_type_to_category",
    "detect_business_heuristics",
    "assign_categories_enhanced",
]

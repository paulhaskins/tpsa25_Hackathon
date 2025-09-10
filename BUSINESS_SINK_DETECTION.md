# Enhanced Business/Sink Detection

This document describes the enhanced business and sink detection features added to the TPSA25 traffic modeling toolkit.

## 🎯 Overview

The enhanced business/sink detection system provides realistic demand flows by identifying and properly categorizing:
- **Business Areas**: Offices, shops, restaurants, commercial zones
- **Transport Hubs**: Stations, airports, bus stops, major intersections
- **Educational Facilities**: Schools, universities, colleges
- **Medical Facilities**: Hospitals, clinics, pharmacies
- **Residential Areas**: Housing, apartments, residential zones

## 🏢 Features

### 1. OSM POI Integration
- **OSMnx Integration**: Query OpenStreetMap for Points of Interest
- **Comprehensive POI Types**: Schools, hospitals, shops, offices, transport facilities
- **Spatial Mapping**: Map POIs to nearest road network nodes
- **Distance Thresholds**: Configurable maximum distance for POI-to-node mapping

### 2. Google Places API Integration (Optional)
- **Major Business Locations**: Shopping malls, airports, government buildings
- **High-Quality Data**: Google's curated place information
- **API Key Support**: Environment variable `GOOGLE_API_KEY`
- **Fallback Graceful**: Works without API key

### 3. Fallback Heuristics
- **City Center Detection**: Identify business areas near city center
- **Connectivity Analysis**: High-degree nodes as business hubs
- **Distance-Based**: Nodes within 2-5km of center with 3+ connections
- **Robust Fallback**: Works when POI data unavailable

### 4. Enhanced Population Capacity
- **Business-Specific Capacities**: Higher capacity for business areas (500 vs 200)
- **Employee + Visitor Model**: Accounts for both workers and customers
- **Category-Based Assignment**: Different capacities per category
- **POI-Based Estimation**: Realistic capacity based on facility type

### 5. Updated Visualization
- **New Color Scheme**:
  - 🏠 Residential = Blue
  - 🏢 Business = Red
  - 🏫 School = Green
  - 🏥 Hospital = Purple
  - 🚌 Transport = Orange
  - ⚪ Other = Gray
- **Enhanced Popups**: Show category, capacity, demand profile
- **Updated Legend**: Reflects new color scheme
- **Business/Sink Highlighting**: Clear visual distinction

## 🚀 Usage

### Command Line Interface
```bash
# Enhanced map with business/sink detection
traffic-model map --place "Dublin, Ireland" \
    --with-population \
    --time-of-day morning \
    --use-osm-pois \
    --use-google-places \
    --use-heuristics \
    --out dublin_business_morning.html

# Disable specific detection methods
traffic-model map --place "Dublin, Ireland" \
    --with-population \
    --use-osm-pois \
    --use-google-places=false \
    --use-heuristics=false \
    --out dublin_osm_only.html
```

### Python API
```python
from traffic_model.categories import assign_categories_enhanced
from traffic_model.population import assign_population_capacity_enhanced
from traffic_model.viz import save_enhanced_folium_map

# Enhanced category assignment
G = assign_categories_enhanced(
    G, 
    "Dublin, Ireland",
    use_osm=True,      # Use OSM POI data
    use_google=True,   # Use Google Places API
    use_heuristics=True # Use fallback heuristics
)

# Enhanced population capacity
G = assign_population_capacity_enhanced(G)

# Create enhanced map
save_enhanced_folium_map(G, "output.html", time_of_day="morning")
```

## 🔧 Configuration

### OSM POI Types
The system queries these OSM POI categories:
```python
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
```

### Google Places Types
```python
place_types = [
    'shopping_mall', 'airport', 'train_station', 'bus_station',
    'hospital', 'university', 'school', 'government', 'bank',
    'restaurant', 'lodging', 'tourist_attraction'
]
```

### Enhanced Capacity Mappings
```python
DEFAULT_CAPACITY = {
    "Residential": 100,
    "Business": 500,    # Increased for business areas
    "School": 500,
    "Hospital": 300,    # Increased for medical facilities
    "Transport": 2000,
    "Other": 50,
}
```

## 📊 Results

### Before Enhancement
- Most nodes classified as "Other"
- Generic capacity assignment
- Limited demand flow realism
- Basic visualization

### After Enhancement
- **Realistic Business Detection**: Offices, shops, restaurants properly identified
- **Transport Hub Recognition**: Stations, airports, major intersections
- **Educational Facility Mapping**: Schools, universities, colleges
- **Medical Facility Identification**: Hospitals, clinics, pharmacies
- **Enhanced Capacity Assignment**: Category-specific, realistic capacities
- **Improved Visualization**: Clear color coding, enhanced popups

## 🧪 Testing

### Test Coverage
- **POI Classification**: Test category assignment for different POI types
- **OSM Integration**: Mock OSM POI data and mapping
- **Google Places**: Mock Google Places API responses
- **Heuristics**: Business detection algorithm testing
- **Enhanced Assignment**: Complete workflow testing

### Running Tests
```bash
# Run enhanced category tests
python -m pytest tests/test_categories_enhanced.py -v

# Run specific test
python -m pytest tests/test_categories_enhanced.py::test_assign_categories_enhanced -v
```

## 🔧 Dependencies

### Required
- `networkx` - Graph processing
- `pandas` - Data manipulation
- `numpy` - Numerical operations

### Optional (for enhanced features)
- `osmnx` - OSM POI querying
- `googlemaps` - Google Places API
- `geopandas` - Spatial data processing
- `shapely` - Geometric operations

### Installation
```bash
# Basic installation
pip install networkx pandas numpy

# Enhanced features
pip install osmnx googlemaps geopandas shapely
```

## 🎯 Example Output

### Category Distribution
```
Category assignment summary:
  Business: 45 nodes
  Residential: 120 nodes
  School: 8 nodes
  Hospital: 3 nodes
  Transport: 12 nodes
  Other: 25 nodes
```

### Population Capacity Summary
```
Population capacity summary:
  Total capacity: 45,230
  Average capacity: 215.4
  Categories: ['Business', 'Residential', 'School', 'Hospital', 'Transport', 'Other']
```

### Map Features
- **Business nodes (red)**: Properly sized and colored
- **School nodes (green)**: Educational facilities highlighted
- **Hospital nodes (purple)**: Medical facilities identified
- **Transport nodes (orange)**: Transport hubs marked
- **Residential nodes (blue)**: Housing areas distinguished
- **Enhanced popups**: Category, capacity, demand profile
- **Updated legend**: New color scheme

## 🚀 Benefits

1. **Realistic Demand Flows**: Business and transport hubs properly identified
2. **Better Traffic Modeling**: Accurate source/sink detection
3. **Enhanced Visualization**: Clear category distinction
4. **Flexible Configuration**: Multiple detection methods
5. **Robust Fallbacks**: Works with or without external APIs
6. **Comprehensive Testing**: Full test coverage
7. **Easy Integration**: Seamless CLI and API integration

This enhanced business/sink detection system transforms the traffic modeling toolkit from a basic "roads + others" system into a sophisticated urban traffic analysis platform with realistic demand patterns and clear visual distinction between different types of urban facilities.

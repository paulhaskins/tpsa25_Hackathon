"""
SCAT Flow Mapping System

This module provides functionality to process SCAT (Sydney Coordinated Adaptive Traffic System)
detector data and create interactive flow maps showing traffic patterns across Dublin.
"""

import zipfile
import pandas as pd
import geopandas as gpd
import folium
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime
import os


def load_detector_lookup(detector_lookup_path: Path) -> gpd.GeoDataFrame:
    """
    Load the detector location lookup table from shapefile.
    
    Args:
        detector_lookup_path: Path to the detector lookup shapefile
        
    Returns:
        GeoDataFrame with detector locations and metadata
    """
    print(f"Loading detector lookup table from: {detector_lookup_path}")
    gdf = gpd.read_file(str(detector_lookup_path))
    
    # Convert coordinates if needed (assuming they're in Irish Grid)
    if 'Lat' in gdf.columns and 'Long' in gdf.columns:
        # If coordinates are in Irish Grid, convert to WGS84
        if gdf['Lat'].max() > 90 or gdf['Long'].max() > 180:
            print("Converting coordinates from Irish Grid to WGS84...")
            # Set CRS to Irish Grid
            gdf = gdf.set_crs('EPSG:2157')
            # Convert to WGS84
            gdf = gdf.to_crs('EPSG:4326')
            # Update Lat/Long columns
            gdf['Lat'] = gdf.geometry.y
            gdf['Long'] = gdf.geometry.x
    
    print(f"Loaded {len(gdf)} detector locations")
    return gdf


def process_scat_zip_file(zip_path: Path, detector_lookup: gpd.GeoDataFrame, 
                         chunk_size: int = 10000) -> pd.DataFrame:
    """
    Process a single SCAT zip file and return hourly averages per detector.
    
    Args:
        zip_path: Path to the SCAT zip file
        detector_lookup: GeoDataFrame with detector locations
        chunk_size: Number of rows to process at a time
        
    Returns:
        DataFrame with hourly averages per detector
    """
    print(f"Processing SCAT file: {zip_path.name}")
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Get the CSV file from the zip
        csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
        if not csv_files:
            print(f"Warning: No CSV files found in {zip_path}")
            return pd.DataFrame()
        
        csv_file = csv_files[0]
        print(f"Processing CSV: {csv_file}")
        
        # Process in chunks to avoid memory issues
        detector_hourly_data = {}
        
        with zip_ref.open(csv_file) as f:
            chunk_iter = pd.read_csv(f, chunksize=chunk_size)
            
            for chunk_num, chunk in enumerate(chunk_iter):
                if chunk_num % 10 == 0:
                    print(f"  Processing chunk {chunk_num + 1}...")
                
                # Parse datetime and extract hour
                chunk['End_Time'] = pd.to_datetime(chunk['End_Time'], format='%Y%m%d%H%M%S', errors='coerce')
                chunk['Hour'] = chunk['End_Time'].dt.hour
                
                # Group by Site and Hour, calculate average volume
                hourly_avg = chunk.groupby(['Site', 'Hour'])['Sum_Volume'].mean().reset_index()
                
                # Accumulate data
                for _, row in hourly_avg.iterrows():
                    site = row['Site']
                    hour = row['Hour']
                    volume = row['Sum_Volume']
                    
                    if site not in detector_hourly_data:
                        detector_hourly_data[site] = {}
                    detector_hourly_data[site][hour] = volume
    
    # Convert to DataFrame
    if not detector_hourly_data:
        return pd.DataFrame()
    
    # Create a comprehensive DataFrame with all hours for all detectors
    all_sites = list(detector_hourly_data.keys())
    all_hours = list(range(24))
    
    rows = []
    for site in all_sites:
        site_data = detector_hourly_data[site]
        for hour in all_hours:
            volume = site_data.get(hour, 0)  # Default to 0 if no data
            rows.append({
                'Site': site,
                'Hour': hour,
                'Avg_Volume': volume
            })
    
    result_df = pd.DataFrame(rows)
    
    # Join with detector lookup to get coordinates
    result_df = result_df.merge(
        detector_lookup[['SiteID', 'Site_Descr', 'Lat', 'Long']], 
        left_on='Site', 
        right_on='SiteID', 
        how='left'
    )
    
    print(f"Processed {len(result_df)} records for {len(all_sites)} detectors")
    return result_df


def create_detector_summary(detector_hourly_data: pd.DataFrame) -> pd.DataFrame:
    """
    Create a summary DataFrame with detector-level statistics.
    
    Args:
        detector_hourly_data: DataFrame with hourly data per detector
        
    Returns:
        Summary DataFrame with detector statistics
    """
    if detector_hourly_data.empty:
        return pd.DataFrame()
    
    # Calculate summary statistics per detector
    summary = detector_hourly_data.groupby(['Site', 'Site_Descr', 'Lat', 'Long']).agg({
        'Avg_Volume': ['mean', 'max', 'sum', 'std']
    }).reset_index()
    
    # Flatten column names
    summary.columns = ['Site', 'Site_Descr', 'Lat', 'Long', 'Daily_Avg', 'Peak_Hour', 'Daily_Total', 'Std_Dev']
    
    # Fill NaN values
    summary = summary.fillna(0)
    
    # Create hourly breakdown
    hourly_breakdown = detector_hourly_data.pivot_table(
        index=['Site', 'Site_Descr', 'Lat', 'Long'], 
        columns='Hour', 
        values='Avg_Volume', 
        fill_value=0
    ).reset_index()
    
    # Flatten hourly columns
    hourly_cols = [f'Hour_{h:02d}' for h in range(24)]
    hourly_breakdown.columns = ['Site', 'Site_Descr', 'Lat', 'Long'] + hourly_cols
    
    # Merge summary with hourly breakdown
    final_summary = summary.merge(hourly_breakdown, on=['Site', 'Site_Descr', 'Lat', 'Long'])
    
    return final_summary


def create_scat_flow_map(detector_summary: pd.DataFrame, output_path: Path) -> None:
    """
    Create an interactive Folium map showing SCAT detector flow data.
    
    Args:
        detector_summary: DataFrame with detector summary data
        output_path: Path to save the HTML map
    """
    if detector_summary.empty:
        print("No detector data available for mapping")
        return
    
    # Calculate map center (Dublin)
    center_lat = detector_summary['Lat'].mean()
    center_lon = detector_summary['Long'].mean()
    
    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Define color scale based on daily average flow
    max_flow = detector_summary['Daily_Avg'].max()
    min_flow = detector_summary['Daily_Avg'].min()
    
    def get_color(flow):
        """Get color based on flow rate"""
        if flow == 0:
            return 'gray'
        elif flow < min_flow + (max_flow - min_flow) * 0.25:
            return 'green'
        elif flow < min_flow + (max_flow - min_flow) * 0.5:
            return 'yellow'
        elif flow < min_flow + (max_flow - min_flow) * 0.75:
            return 'orange'
        else:
            return 'red'
    
    def get_size(flow):
        """Get marker size based on flow rate"""
        if flow == 0:
            return 5
        else:
            return max(5, min(20, int(5 + (flow / max_flow) * 15)))
    
    # Add markers for each detector
    for _, row in detector_summary.iterrows():
        if pd.isna(row['Lat']) or pd.isna(row['Long']):
            continue
            
        # Create hourly flow table for popup
        hourly_data = []
        for hour in range(24):
            flow = row[f'Hour_{hour:02d}']
            hourly_data.append(f"Hour {hour:02d}: {flow:.1f}")
        
        hourly_table = "<br>".join(hourly_data)
        
        # Create popup content
        popup_content = f"""
        <div style="font-family: Arial; font-size: 12px;">
            <b>Detector: {row['Site']}</b><br>
            <b>Location: {row['Site_Descr']}</b><br><br>
            <b>Daily Average: {row['Daily_Avg']:.1f}</b><br>
            <b>Peak Hour: {row['Peak_Hour']:.1f}</b><br>
            <b>Daily Total: {row['Daily_Total']:.1f}</b><br><br>
            <b>Hourly Breakdown:</b><br>
            {hourly_table}
        </div>
        """
        
        # Add marker
        folium.CircleMarker(
            location=[row['Lat'], row['Long']],
            radius=get_size(row['Daily_Avg']),
            popup=folium.Popup(popup_content, max_width=300),
            color='black',
            weight=1,
            fillColor=get_color(row['Daily_Avg']),
            fillOpacity=0.7,
            tooltip=f"Site {row['Site']}: {row['Daily_Avg']:.1f} avg flow"
        ).add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>Flow Rate Legend</b></p>
    <p><i class="fa fa-circle" style="color:gray"></i> No Data</p>
    <p><i class="fa fa-circle" style="color:green"></i> Low Flow</p>
    <p><i class="fa fa-circle" style="color:yellow"></i> Medium Flow</p>
    <p><i class="fa fa-circle" style="color:orange"></i> High Flow</p>
    <p><i class="fa fa-circle" style="color:red"></i> Very High Flow</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save map
    m.save(str(output_path))
    print(f"SCAT flow map saved to: {output_path}")


def make_scat_flow_map(zip_paths: List[Path], detector_lookup_path: Path, 
                      output_map: Path, output_csv: Path, 
                      chunk_size: int = 10000, force_reprocess: bool = False) -> None:
    """
    Main function to process SCAT data and create flow map.
    
    Args:
        zip_paths: List of paths to SCAT zip files
        detector_lookup_path: Path to detector lookup shapefile
        output_map: Path to save the HTML map
        output_csv: Path to save the detector summary CSV
        chunk_size: Number of rows to process at a time
        force_reprocess: If True, reprocess even if summary CSV exists
    """
    print("Starting SCAT flow mapping process...")
    
    # Check if summary CSV already exists
    if output_csv.exists() and not force_reprocess:
        print(f"Using cached detector summary: {output_csv}")
        detector_summary = pd.read_csv(output_csv)
    else:
        # Load detector lookup table
        detector_lookup = load_detector_lookup(detector_lookup_path)
        
        # Process all zip files
        all_detector_data = []
        
        for zip_path in zip_paths:
            if not zip_path.exists():
                print(f"Warning: File not found: {zip_path}")
                continue
                
            detector_data = process_scat_zip_file(zip_path, detector_lookup, chunk_size)
            if not detector_data.empty:
                all_detector_data.append(detector_data)
        
        if not all_detector_data:
            print("No SCAT data processed successfully")
            return
        
        # Combine all detector data
        print("Combining data from all files...")
        combined_data = pd.concat(all_detector_data, ignore_index=True)
        
        # Calculate final averages across all files
        print("Calculating final averages...")
        final_data = combined_data.groupby(['Site', 'Site_Descr', 'Lat', 'Long', 'Hour'])['Avg_Volume'].mean().reset_index()
        
        # Create detector summary
        detector_summary = create_detector_summary(final_data)
        
        # Save summary CSV
        detector_summary.to_csv(output_csv, index=False)
        print(f"Detector summary saved to: {output_csv}")
    
    # Create flow map
    create_scat_flow_map(detector_summary, output_map)
    
    print("SCAT flow mapping process completed!")


def load_scat_sensor_data() -> Optional[pd.DataFrame]:
    """
    Load SCAT sensor data with flow rates for different times of day.
    
    Returns:
        DataFrame with SCAT sensor data including coordinates and flow rates
    """
    try:
        # Load detector lookup table
        detector_lookup_path = Path("data/raw/scats/dcc_traffic_signal_sites_20221130.shp")
        if not detector_lookup_path.exists():
            print("SCAT detector lookup file not found")
            return None
        
        detector_lookup = load_detector_lookup(detector_lookup_path)
        
        # Try to load recent SCAT data
        data_dir = Path("data/raw/scats")
        recent_files = get_recent_scat_files(data_dir, months_back=1)
        
        if not recent_files:
            print("No recent SCAT files found")
            return None
        
        # Process the most recent file
        recent_file = recent_files[0]
        detector_data = process_scat_zip_file(recent_file, detector_lookup, chunk_size=5000)
        
        if detector_data.empty:
            print("No SCAT data processed")
            return None
        
        # Create summary with hourly flow rates
        detector_summary = create_detector_summary(detector_data)
        
        # Filter to only include sensors with valid coordinates
        valid_sensors = detector_summary[
            (detector_summary['Lat'].notna()) & 
            (detector_summary['Long'].notna()) &
            (detector_summary['Daily_Avg'] > 0)
        ].copy()
        
        print(f"Loaded {len(valid_sensors)} valid SCAT sensors")
        return valid_sensors
        
    except Exception as e:
        print(f"Error loading SCAT sensor data: {e}")
        return None


def get_recent_scat_files(data_dir: Path, months_back: int = 3) -> List[Path]:
    """
    Get the most recent SCAT files from the data directory.
    
    Args:
        data_dir: Path to the SCAT data directory
        months_back: Number of months back to look for files
        
    Returns:
        List of paths to recent SCAT zip files
    """
    zip_files = []
    
    # Look in recent year directories
    current_year = datetime.now().year
    for year in range(current_year - 1, current_year + 1):
        year_dir = data_dir / str(year)
        if year_dir.exists():
            for zip_file in year_dir.glob("*.zip"):
                zip_files.append(zip_file)
    
    # Sort by modification time (most recent first)
    zip_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    # Return the most recent files
    return zip_files[:months_back * 2]  # Assume ~2 files per month


if __name__ == "__main__":
    # Example usage
    data_dir = Path("data/raw/scats")
    detector_lookup_path = data_dir / "dcc_traffic_signal_sites_20221130.shp"
    
    # Get recent SCAT files
    recent_files = get_recent_scat_files(data_dir, months_back=2)
    print(f"Found {len(recent_files)} recent SCAT files")
    
    if recent_files and detector_lookup_path.exists():
        make_scat_flow_map(
            zip_paths=recent_files,
            detector_lookup_path=detector_lookup_path,
            output_map=Path("scat_flow_map.html"),
            output_csv=Path("scat_detector_summary.csv")
        )
    else:
        print("No SCAT files or detector lookup found")

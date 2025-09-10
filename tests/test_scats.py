"""Tests for SCATS data processing functionality."""

import pandas as pd
import zipfile
import tempfile
from pathlib import Path
from src.datahub.scats import (
    read_scats_zip,
    unpack_all_scats_archives,
    aggregate_scats_demand_profiles,
    load_scats_profiles,
    process_all_scats_data,
    _extract_year_from_filename,
    _extract_month_from_filename,
    _standardize_scats_columns
)


def test_extract_year_from_filename():
    """Test year extraction from SCATS filenames."""
    assert _extract_year_from_filename("scats_2024_january.zip") == 2024
    assert _extract_year_from_filename("scats2023march.zip") == 2023
    assert _extract_year_from_filename("scatsjanuary2025.zip") == 2025
    assert _extract_year_from_filename("scats.zip") == 2020  # Default fallback


def test_extract_month_from_filename():
    """Test month extraction from SCATS filenames."""
    assert _extract_month_from_filename("scats_2024_january.zip") == "january"
    assert _extract_month_from_filename("scats2023march.zip") == "march"
    assert _extract_month_from_filename("scatsjan2025.zip") == "january"
    assert _extract_month_from_filename("scats.zip") == "unknown"  # Default fallback


def test_standardize_scats_columns():
    """Test SCATS column standardization."""
    # Test with typical SCATS columns
    df = pd.DataFrame({
        'timestamp': ['2024-01-01 08:00:00', '2024-01-01 09:00:00'],
        'site_id': [1, 2],
        'sum_volume': [100, 150],
        'avg_volume': [50, 75],
        'region': ['Dublin', 'Cork']
    })
    
    standardized = _standardize_scats_columns(df)
    
    # Check that columns were renamed
    assert 'End_Time' in standardized.columns
    assert 'Site' in standardized.columns
    assert 'Sum_Volume' in standardized.columns
    assert 'Avg_Volume' in standardized.columns
    assert 'Region' in standardized.columns


def test_read_scats_zip(tmp_path: Path):
    """Test reading SCATS data from a ZIP file."""
    # Create test CSV data
    test_data = pd.DataFrame({
        'End Time': ['2024-01-01 08:00:00', '2024-01-01 09:00:00'],
        'Site ID': [1, 2],
        'Sum Volume': [100, 150],
        'Avg Volume': [50, 75],
        'Region': ['Dublin', 'Cork']
    })
    
    # Create temporary ZIP file
    zip_path = tmp_path / "test_scats.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("scats_data.csv", test_data.to_csv(index=False))
    
    # Read the ZIP file
    result_df = read_scats_zip(zip_path)
    
    # Check the result
    assert len(result_df) == 2
    assert 'timestamp' in result_df.columns
    assert 'site_id' in result_df.columns
    assert 'sum_volume' in result_df.columns
    assert 'avg_volume' in result_df.columns
    assert 'region' in result_df.columns
    
    # Check data types
    assert pd.api.types.is_datetime64_any_dtype(result_df['timestamp'])
    assert pd.api.types.is_integer_dtype(result_df['site_id'])


def test_aggregate_scats_demand_profiles(tmp_path: Path):
    """Test SCATS demand profile aggregation."""
    # Create test combined SCATS data
    combined_df = pd.DataFrame({
        'End_Time': pd.date_range('2024-01-01', periods=48, freq='H'),
        'Site': [1, 1, 2, 2] * 12,  # 2 sites, 24 hours each
        'Sum_Volume': [100, 120, 80, 90] * 12,
        'Avg_Volume': [50, 60, 40, 45] * 12,
        'Region': ['Dublin', 'Dublin', 'Cork', 'Cork'] * 12
    })
    
    # Aggregate demand profiles
    profiles = aggregate_scats_demand_profiles(combined_df, tmp_path)
    
    # Check the result
    assert len(profiles) > 0
    assert 'Site' in profiles.columns
    assert 'hour' in profiles.columns
    assert 'Sum_Volume' in profiles.columns
    assert 'Avg_Volume' in profiles.columns
    assert 'Region' in profiles.columns
    
    # Check that we have data for both sites
    unique_sites = profiles['Site'].unique()
    assert len(unique_sites) == 2
    assert 1 in unique_sites
    assert 2 in unique_sites
    
    # Check that we have hourly data
    unique_hours = profiles['hour'].unique()
    assert len(unique_hours) == 24
    assert all(0 <= h <= 23 for h in unique_hours)


def test_load_scats_profiles(tmp_path: Path):
    """Test loading SCATS demand profiles from file."""
    # Create test profiles data
    profiles_data = pd.DataFrame({
        'Site': [1, 1, 2, 2],
        'hour': [8, 9, 8, 9],
        'Sum_Volume': [100, 120, 80, 90],
        'Avg_Volume': [50, 60, 40, 45],
        'Region': ['Dublin', 'Dublin', 'Cork', 'Cork']
    })
    
    # Save to file
    profiles_file = tmp_path / "test_profiles.csv"
    profiles_data.to_csv(profiles_file, index=False)
    
    # Load profiles
    loaded_profiles = load_scats_profiles(profiles_file)
    
    # Check the result
    assert len(loaded_profiles) == 4
    assert 'Site' in loaded_profiles.columns
    assert 'hour' in loaded_profiles.columns
    assert 'Sum_Volume' in loaded_profiles.columns
    assert 'Avg_Volume' in loaded_profiles.columns
    assert 'Region' in loaded_profiles.columns


def test_scats_processing_pipeline_smoke_test(tmp_path: Path):
    """Smoke test for the complete SCATS processing pipeline."""
    # Create a mock SCATS directory with test ZIP files
    scats_dir = tmp_path / "scats"
    scats_dir.mkdir()
    
    # Create test ZIP files
    for i, (year, month) in enumerate([(2024, "january"), (2024, "february")]):
        zip_path = scats_dir / f"scats_{year}_{month}.zip"
        
        # Create test CSV data
        test_data = pd.DataFrame({
            'End Time': pd.date_range(f'{year}-01-01', periods=24, freq='H'),
            'Site ID': [i + 1] * 24,
            'Sum Volume': [100 + i * 10] * 24,
            'Avg Volume': [50 + i * 5] * 24,
            'Region': ['Dublin'] * 24
        })
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("scats_data.csv", test_data.to_csv(index=False))
    
    # Run the processing pipeline
    output_dir = tmp_path / "output"
    demand_profiles = process_all_scats_data(scats_dir, output_dir)
    
    # Check the result
    assert len(demand_profiles) > 0
    assert 'Site' in demand_profiles.columns
    assert 'hour' in demand_profiles.columns
    assert 'Sum_Volume' in demand_profiles.columns
    assert 'Avg_Volume' in demand_profiles.columns
    
    # Check that output files were created
    assert (output_dir / "scats_combined_data.csv").exists()
    assert (output_dir / "scats_demand_profiles.csv").exists()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))

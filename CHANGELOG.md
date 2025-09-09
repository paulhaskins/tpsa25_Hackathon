# Changelog

All notable changes to the TPSA Traffic Toolkit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-09

### Added
- **Data Hub CLI**: Complete data ingestion utilities for SCATS and TII data sources
  - `datahub scats-list`: List available SCATS datasets from Smart Dublin
  - `datahub scats-get`: Download specific month/year SCATS data
  - `datahub tii-list`: List TII portal resources
  - `datahub tii-load`: Load TII traffic count exports
- **Traffic Simulation Package**: Comprehensive simulation engine
  - Capacity-aware probabilistic traffic flows
  - Synthetic graph generation and OSM integration  
  - Demo and OSM-based CLI commands
  - Folium visualization with time-step maps
- **Console Script Entry Points**: Proper packaging with CLI commands
  - `traffic-model`: Graph building and analysis
  - `traffic-sim`: Traffic simulation demos
  - `datahub`: Data ingestion utilities
- **Comprehensive Test Suite**: 10 passing tests across all modules
  - Unit tests for all components
  - Integration test (`quick_test.py`)
  - Smoke tests for simulation engine

### Fixed
- **Import System**: Resolved missing function imports in `__init__.py` files
- **SCATS Data Fetching**: Fixed regex patterns and duplicate function definitions
- **NetworkX Compatibility**: Resolved duplicate key arguments in `add_edge()` calls
- **Test Monkeypatching**: Fixed module targeting for proper test isolation
- **HTTP Response Mocking**: Added missing methods to fake response objects

### Changed
- **Project Structure**: Reorganized into three main packages under `src/`
- **Package Metadata**: Updated `pyproject.toml` with proper dependencies and scripts
- **Documentation**: Comprehensive README.md and added CONTRIBUTING.md
- **License**: Clarified MIT license with proper attribution

### Technical Details
- Python 3.10+ support with type hints throughout
- Dependencies: OSMnx, NetworkX, Pandas, Folium, Typer, etc.
- Src-layout package structure with proper setuptools configuration
- CI/CD ready with pytest configuration

## [0.1.0] - 2024-12-XX

### Added
- Initial traffic_model package for graph building and analysis
- OpenStreetMap integration via OSMnx
- Neighborhood detection and supernode simplification
- Basic flow attachment and Folium visualization
- CSV data loading utilities

### Infrastructure
- Basic project structure and dependencies
- Initial test framework
- GitHub Actions CI setup

---

## Release Notes

### Version 0.2.0 Highlights

This release transforms the project from a basic traffic model into a comprehensive toolkit with three integrated components:

1. **Enhanced Traffic Modelling**: Improved graph loading, neighborhood detection, and flow analysis
2. **New Simulation Engine**: Complete probabilistic traffic simulator with capacity constraints
3. **Data Integration**: Full SCATS and TII data ingestion pipeline

All components work together seamlessly - build graphs with traffic_model, simulate flows with traffic_sim, and feed real data via datahub.

### Breaking Changes
- Package name changed from `traffic-model` to `tpsa-traffic`
- CLI commands now available as console scripts
- Some internal API changes in graph loading functions

### Migration Guide
- Update imports to use new package structure
- Install via `pip install -e .` to get console scripts
- Update CLI calls to use new entry points (`traffic-model`, `traffic-sim`, `datahub`)

### Next Steps
- Real-time data streaming capabilities
- Advanced visualization features
- Machine learning integration for flow prediction
- Docker containerization for deployment

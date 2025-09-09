# Contributing to TPSA Traffic Toolkit

Thank you for your interest in contributing to the TPSA25 traffic modelling, simulation, and data ingestion toolkit!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/tpsa25_Hackathon.git
   cd tpsa25_Hackathon
   ```

2. **Set up Python environment**
   ```bash
   python -m venv .venv
   # Windows PowerShell
   . .venv/Scripts/Activate.ps1
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .  # Install in editable mode
   ```

4. **Run tests to verify setup**
   ```bash
   pytest -v
   ```

## Project Structure

- `src/traffic_model/`: Core traffic modelling (graph building, neighborhood detection, flows)
- `src/traffic_sim/`: Traffic simulation engine
- `src/datahub/`: Data ingestion utilities (SCATS, TII)
- `tests/`: Test suite
- `configs/`: Configuration files
- `docs/`: Documentation

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_data_fetch.py

# Run individual test modules
python tests/test_imports.py
```

### Test Structure
- `test_imports.py` - Import validation
- `test_data_fetch.py` - SCATS data fetching
- `test_flows.py` - Flow processing
- `test_load_graph.py` - Graph loading from CSV
- `test_neighborhoods.py` - Neighborhood detection
- `test_viz.py` - Visualization functionality
- `test_sim_smoke.py` - Traffic simulation smoke tests
- `quick_test.py` - Integration test

## Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings to functions and classes
- Keep line length reasonable (typically 100-120 characters)

## Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write tests for new functionality
   - Update documentation as needed
   - Ensure all tests pass

3. **Test your changes**
   ```bash
   pytest -v
   python tests/quick_test.py  # Integration test
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

## CLI Testing

Test the three main CLI tools:

### traffic_model CLI
```bash
python -m traffic_model.cli --help
python -m traffic_model.cli build --place "Dublin, Ireland" --out data/processed/test.graphml
```

### traffic_sim CLI
```bash
python -m traffic_sim.cli --help  
python -m traffic_sim.cli demo --config configs/demo.yml
```

### datahub CLI
```bash
python -m datahub.cli scats-list
python -m datahub.cli scats-get February 2024 --out data/raw
```

## Data Sources

When working with external data:

- **SCATS (Smart Dublin)**: Respect robots.txt and rate limits
- **TII**: Use manual exports when possible
- **OpenStreetMap**: Follow OSM attribution requirements

## Common Issues

### Import Errors
- Ensure all required functions are exported in `__init__.py` files
- Check for circular imports
- Verify package structure matches imports

### Test Failures
- Monkeypatch issues: Patch the correct module (e.g., `traffic_model.data_fetch.requests`)
- Missing methods in mock objects (add `raise_for_status()` to fake HTTP responses)
- NetworkX edge key conflicts: Remove duplicate keys from attributes

### Performance Issues
- Large graphs can be slow to process
- Test with smaller datasets first
- Consider using synthetic graphs for development

## Documentation

- Update README.md for major changes
- Update WARP.md for terminal usage patterns
- Add docstrings to new functions
- Update requirements.txt if adding dependencies

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG or README with recent changes
3. Ensure all tests pass
4. Tag the release

## Getting Help

- Check existing issues and tests for examples
- Review WARP.md for terminal usage guidance
- Look at the integration test (`quick_test.py`) for end-to-end examples

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

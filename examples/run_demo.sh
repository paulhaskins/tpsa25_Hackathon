#!/usr/bin/env bash
set -euo pipefail

python -m traffic_sim.cli demo --config configs/demo.yml || python -m traffic_sim.cli demo
echo "Outputs written to outputs/"



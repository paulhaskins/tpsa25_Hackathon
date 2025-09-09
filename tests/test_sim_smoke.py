from __future__ import annotations

import datetime as dt

from traffic_sim.graph_loader import make_synthetic, tag_supernodes
from traffic_sim.capacity import edge_capacity
from traffic_sim.demand import build_schedules, inject_sources
from traffic_sim.simulate import run


def test_synthetic_run_smoke() -> None:
    G = make_synthetic(n=4)
    tag_supernodes(G, n_residential=3, n_sinks=2)
    edge_capacity(G, base_cap=8.0)
    schedules = build_schedules({})
    params = {"beta": 0.5, "alpha": 1.0, "dt_minutes": 60}

    start = dt.datetime(2024, 1, 1, 7, 0, 0)
    steps = 5
    t = start
    total_injected = 0.0
    total_arrivals = 0.0
    for _ in range(steps):
        pre_buffers = sum(float(d.get("buffer", 0.0)) for _, d in G.nodes(data=True))
        inject_sources(G, t, schedules)
        post_buffers = sum(float(d.get("buffer", 0.0)) for _, d in G.nodes(data=True))
        total_injected += max(0.0, post_buffers - pre_buffers)
        metrics = run(G, params, schedules, steps=1, start_time=t)
        total_arrivals += metrics[-1]["arrivals"]
        t = t + dt.timedelta(minutes=60)

    # some arrivals should occur
    assert total_arrivals > 0.0
    # conservation (within loose tolerance due to floating rounding):
    total_r = sum(float(d.get("r", 0.0)) for _, _, d in G.edges(data=True))
    buffers = sum(float(d.get("buffer", 0.0)) for _, d in G.nodes(data=True))
    # injected equals arrivals + remaining in system
    assert abs(total_injected - (total_arrivals + total_r + buffers)) < 1e-6


def test_capacity_assignment_and_probs() -> None:
    from traffic_sim.route import precompute_sink_distances, transition_probs

    G = make_synthetic(n=3)
    res, sinks = tag_supernodes(G, n_residential=1, n_sinks=1)
    edge_capacity(G)
    sink_tt = precompute_sink_distances(G)
    # For the residential node, there should be some outgoing probabilities
    res_node = list(res)[0]
    probs = transition_probs(G, res_node, sink_tt, beta=0.5, alpha=1.0)
    assert isinstance(probs, dict)
    # Either no improving edges (empty) or sum to 1
    if probs:
        s = sum(probs.values())
        assert abs(s - 1.0) < 1e-9


def test_viz_output_creation(tmp_path) -> None:
    from traffic_sim.viz import to_folium
    G = make_synthetic(n=3)
    tag_supernodes(G, n_residential=1, n_sinks=1)
    edge_capacity(G)
    out = tmp_path / "map.html"
    to_folium(G, "t00", str(out))
    assert out.exists() and out.stat().st_size > 0



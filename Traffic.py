# ==================== Full Traffic + Density + Correlation Script with PNG Export ====================

import networkx as nx
import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib as mpl
import random
import matplotlib.animation as animation
import scipy.sparse as sp
from matplotlib.collections import LineCollection
import os

# ----------- Parameters -------------
num_nodes = 100
avg_degree = 3
r_max = 20
sample_size = 100

time_steps = 50
tau = 10.0
dt = 1.0
sigma = 5.0
minor_road_prob = 0.7
x_nearest = 3

capacity_per_edge = 20
rho_max = 100
k = 0.5
sink_capacity = 60  # Limit on per-timestep sink inflow

# ----------- Create Graph ------------
G = nx.DiGraph()

# --- Node types ---
sources = random.sample(range(num_nodes), k=int(0.05 * num_nodes))
remaining_nodes = set(range(num_nodes)) - set(sources)
sinks = random.sample(list(remaining_nodes), k=int(0.05 * num_nodes))
internals = list(set(range(num_nodes)) - set(sources) - set(sinks))

node_types = {}
for i in range(num_nodes):
    if i in sources:
        node_types[i] = 'source'
    elif i in sinks:
        node_types[i] = 'sink'
    else:
        node_types[i] = 'internal'

external_flow = {}
for i in range(num_nodes):
    if node_types[i] == 'source':
        external_flow[i] = random.randint(15, 50)
    elif node_types[i] == 'sink':
        external_flow[i] = 0  # sinks start empty
    else:
        external_flow[i] = 0

# --- Add nodes with inflow/outflow and S (external source/sink term)
for i in range(num_nodes):
    internal_inflow = random.randint(10, 50)
    internal_outflow = random.randint(10, 50)
    total_inflow = internal_inflow + max(0, external_flow[i])
    total_outflow = internal_outflow + abs(min(0, external_flow[i]))
    G.add_node(i,
               inflow=total_inflow,
               outflow=total_outflow,
               node_type=node_types[i],
               S=external_flow[i])

# --- Node capacities
for i in range(num_nodes):
    if node_types[i] == 'sink':
        G.nodes[i]['capacity'] = rho_max  # sinks can accumulate up to rho_max
    else:
        G.nodes[i]['capacity'] = G.nodes[i]['inflow']  # others capped by inflow

# --- Node positions ---
grid_size = int(np.ceil(np.sqrt(num_nodes)))
positions = {i: (i % grid_size, i // grid_size) for i in range(num_nodes)}

# --- Edge creation avoiding sink-to-sink edges ---
for i in range(num_nodes):
    targets = set()
    while len(targets) < avg_degree:
        t = random.randint(0, num_nodes - 1)
        if t == i:
            continue
        if node_types[i] == 'source' and node_types[t] == 'source':
            continue
        if node_types[i] == 'sink' and node_types[t] == 'sink':
            continue
        prob = 0.7 if node_types[t] == 'sink' else 0.3
        if random.random() > prob:
            continue
        targets.add(t)
    for t in targets:
        G.add_edge(i, t)
        if node_types[i] == 'internal' and node_types[t] == 'internal':
            G.add_edge(t, i)

# --- Helper: segments intersect ---
def segments_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])
    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))

# --- Add minor roads avoiding crossings ---
def remove_edge_crossings_and_add_minor_roads(G, positions, minor_road_prob=0.5):
    edges = list(G.edges())
    crossing_edges = set()
    for i in range(len(edges)):
        u1, v1 = edges[i]
        p1, p2 = positions[u1], positions[v1]
        for j in range(i + 1, len(edges)):
            u2, v2 = edges[j]
            if len({u1, v1, u2, v2}) < 4:
                continue
            p3, p4 = positions[u2], positions[v2]
            if segments_intersect(p1, p2, p3, p4):
                crossing_edges.add((u1, v1))
                crossing_edges.add((u2, v2))
    for e in crossing_edges:
        if G.has_edge(*e):
            G.remove_edge(*e)
    # Minor roads
    node_list = list(G.nodes())
    for i in node_list:
        for j in node_list:
            if i == j or G.has_edge(i, j):
                continue
            dist = np.linalg.norm(np.array(positions[i]) - np.array(positions[j]))
            if dist > 1.5 or random.random() > minor_road_prob:
                continue
            can_add_ij = can_add_ji = True
            for (u, v) in G.edges():
                if len({i, j, u, v}) < 4:
                    continue
                if segments_intersect(positions[i], positions[j], positions[u], positions[v]):
                    can_add_ij = False
                if segments_intersect(positions[j], positions[i], positions[u], positions[v]):
                    can_add_ji = False
                if not can_add_ij and not can_add_ji:
                    break
            if can_add_ij and G.nodes[i]['node_type'] != 'sink' and G.nodes[j]['node_type'] != 'sink':
                G.add_edge(i, j)
            if can_add_ji and G.nodes[j]['node_type'] != 'sink' and G.nodes[i]['node_type'] != 'sink':
                G.add_edge(j, i)

remove_edge_crossings_and_add_minor_roads(G, positions, minor_road_prob=minor_road_prob)

# --- Ensure connectivity to sinks ---
def ensure_connectivity_to_sink(G, sinks, positions):
    for node in G.nodes():
        if G.nodes[node]['node_type'] == 'sink':
            continue
        if any(nx.has_path(G, node, sink) for sink in sinks):
            continue
        candidates = [n for n in G.nodes() if n != node and n not in sinks]
        candidates = sorted(candidates, key=lambda n: np.linalg.norm(np.array(positions[n]) - np.array(positions[node])))
        for target in candidates:
            if any(nx.has_path(G, target, sink) for sink in sinks):
                G.add_edge(node, target)
                break

ensure_connectivity_to_sink(G, sinks, positions)

# --- Connect sinks if they have no incoming edges ---
def connect_sinks_to_network(G, sinks, positions, max_attempts=10):
    non_sinks = [n for n in G.nodes if G.nodes[n]['node_type'] != 'sink']
    for sink in sinks:
        if G.in_degree(sink) > 0:
            continue
        distances = {n: np.linalg.norm(np.array(positions[n]) - np.array(positions[sink])) for n in non_sinks}
        sorted_nodes = sorted(distances, key=distances.get)
        for node in sorted_nodes[:max_attempts]:
            if not G.has_edge(node, sink):
                G.add_edge(node, sink)
                break

connect_sinks_to_network(G, sinks, positions)

# ================= Vectorized density evolution =================
num_nodes = G.number_of_nodes()
rho_current = np.array([0 if G.nodes[i]['node_type']=='sink' else G.nodes[i]['inflow'] for i in range(num_nodes)], dtype=float)
S = np.array([G.nodes[i]['S'] for i in range(num_nodes)], dtype=float)

A_out = nx.adjacency_matrix(G, nodelist=range(num_nodes)).tocsc()
A_in = A_out.transpose().tocsc()

# --- Sink attraction factor ---
sink_distances = {}
for node in G.nodes():
    lengths = nx.single_source_shortest_path_length(G, node)
    d_to_sink = min([lengths[sink] for sink in sinks if sink in lengths] or [np.inf])
    sink_distances[node] = d_to_sink

finite_dists = [d for d in sink_distances.values() if np.isfinite(d)]
max_dist = max(finite_dists) if finite_dists else 1.0
attraction = {node: 1.0 + (max_dist - sink_distances[node])/max_dist*0.5 if np.isfinite(sink_distances[node]) else 1.0
              for node in G.nodes()}

# --- Time evolution ---
rho_t_list = []
delta_t_list = []

for step in range(time_steps):
    congestion = 1 - rho_current / rho_max

    # Inflow
    rows_in, cols_in = A_in.nonzero()
    data_in = k * rho_current[cols_in] * congestion[rows_in]
    data_in = np.clip(data_in, 0, capacity_per_edge)
    F_in = sp.coo_matrix((data_in, (rows_in, cols_in)), shape=A_in.shape).tocsc()
    inflow = np.array(F_in.sum(axis=1)).flatten()
    
    # Cap inflow at sinks
    for sink in sinks:
        inflow[sink] = min(inflow[sink], sink_capacity)

    # Outflow
    rows_out, cols_out = A_out.nonzero()
    data_out = k * rho_current[rows_out] * congestion[cols_out]
    data_out = np.clip(data_out, 0, capacity_per_edge)
    F_out = sp.coo_matrix((data_out, (rows_out, cols_out)), shape=A_out.shape).tocsc()
    outflow = np.array(F_out.sum(axis=1)).flatten()

    # Update density and enforce per-node capacity
    rho_next = rho_current + dt * (inflow - outflow + S)
    for i in range(num_nodes):
        rho_next[i] = min(rho_next[i], G.nodes[i]['capacity'])
        rho_next[i] = max(rho_next[i], 0)

    rho_t_list.append(rho_next)
    mean_rho = np.mean(rho_next)
    delta_next = (rho_next - mean_rho) / mean_rho if mean_rho != 0 else np.zeros_like(rho_next)
    delta_t_list.append(delta_next)
    rho_current = rho_next

# ================== Nearest-neighbor correlations ==================
def get_x_nearest_neighbors(G, x):
    nearest_dict = {}
    for node in G.nodes:
        lengths = nx.single_source_shortest_path_length(G, node)
        filtered = sorted([(n, d) for n, d in lengths.items() if n != node], key=lambda x: x[1])
        nearest_nodes = [n for n, d in filtered[:x]]
        nearest_dict[node] = nearest_nodes
    return nearest_dict

nearest_neighbors = get_x_nearest_neighbors(G, x_nearest)

avg_corr_x_nearest = []
for t in range(time_steps):
    dt_arr = delta_t_list[t]
    corrs = []
    for i in G.nodes:
        for nn in nearest_neighbors[i]:
            corrs.append(dt_arr[i] * dt_arr[nn])
    # Normalized between -1 and 1
    if corrs:
        min_c, max_c = min(corrs), max(corrs)
        if max_c - min_c > 0:
            corrs_norm = [(c - min_c)/(max_c - min_c)*2 - 1 for c in corrs]
        else:
            corrs_norm = [0]*len(corrs)
        avg_corr_x_nearest.append(np.mean(corrs_norm))
    else:
        avg_corr_x_nearest.append(0)

print("\n✅ Average adjacency correlation over x nearest neighbors (normalized):")
print(avg_corr_x_nearest)

# ---------------- Combined Animation (Updated for PNG export) ----------------
# ---------------- Combined Animation (Updated for PNG export) ----------------
fig, ax = plt.subplots(figsize=(10,10))
ax.axis('off')
ax.set_title('Node Density (ρ_i) + Edge Correlation (δ_iδ_j)')

edges_list = list(G.edges())
edge_corrs_per_frame = [
    [delta_t_list[f][u]*delta_t_list[f][v] for (u,v) in edges_list]
    for f in range(time_steps)
]

# Define source/sink nodes for clarity
source_nodes = sources
sink_nodes = sinks


# Edge collection (drawn first, zorder=1)
cmap_edge = plt.cm.coolwarm
all_edge_vals = [val for frame in edge_corrs_per_frame for val in frame]
norm_edge = mpl.colors.Normalize(vmin=min(all_edge_vals), vmax=max(all_edge_vals))
edge_segments = [(positions[u], positions[v]) for (u,v) in edges_list]
edge_collection = LineCollection(edge_segments, cmap=cmap_edge, norm=norm_edge, linewidths=2.0, zorder=1)
edge_collection.set_array(np.array(edge_corrs_per_frame[0]))
ax.add_collection(edge_collection)

# Node color map
cmap_rho = plt.cm.viridis
rho_min_val, rho_max_val = 0, max(np.max(rho_t_list), rho_max)
norm_rho = mpl.colors.Normalize(vmin=rho_min_val, vmax=rho_max_val)

# Draw nodes on top of edges
nodes_collection = nx.draw_networkx_nodes(
    G, positions,
    node_color=[cmap_rho(norm_rho(rho_t_list[0][n])) for n in G.nodes()],
    node_size=150,
    ax=ax,
    linewidths=1.5,
    edgecolors='black',
)

# Highlight sources and sinks
nx.draw_networkx_nodes(G, positions, nodelist=source_nodes, node_color='none',
                       edgecolors='green', node_shape='s', node_size=180, linewidths=2.0, ax=ax)
nx.draw_networkx_nodes(G, positions, nodelist=sink_nodes, node_color='none',
                       edgecolors='red', node_shape='^', node_size=180, linewidths=2.0, ax=ax)

# Node density labels
node_texts = {}
for n in G.nodes():
    x, y = positions[n]
    node_texts[n] = ax.text(x, y+0.3, f"{rho_t_list[0][n]:.0f}", ha='center', fontsize=8,
                            color='black', zorder=3)

# Colorbars
cbar_nodes = plt.colorbar(plt.cm.ScalarMappable(norm=norm_rho, cmap=cmap_rho),
                          ax=ax, fraction=0.046, pad=0.04)
cbar_nodes.set_label('Node Density ρ_i')
cbar_edges = plt.colorbar(plt.cm.ScalarMappable(norm=norm_edge, cmap=cmap_edge),
                          ax=ax, fraction=0.046, pad=0.08)
cbar_edges.set_label('Edge Correlation δ_iδ_j')

# Animation update function
def update_combined(frame):
    # Update node colors
    node_colors = [cmap_rho(norm_rho(rho_t_list[frame][n])) for n in G.nodes()]
    nodes_collection.set_facecolor(node_colors)
    
    # Update edge correlations
    edge_collection.set_array(np.array(edge_corrs_per_frame[frame]))
    
    # Update node density labels
    for n in G.nodes():
        val = rho_t_list[frame][n]
        node_texts[n].set_text(f"{val:.0f}")
        if node_types[n] == 'source':
            node_texts[n].set_color('green')
        elif node_types[n] == 'sink':
            node_texts[n].set_color('red')
        else:
            node_texts[n].set_color('black')
    
    # Export every 5th frame as PNG
    if frame % 5 == 0:
        plt.savefig(f'frame_{frame:03d}.png', dpi=200)
    
    ax.set_title(f'Density & Edge Correlation timestep {frame+1}/{time_steps}')
    return nodes_collection, edge_collection, *node_texts.values()

# Create animation
combined_anim = animation.FuncAnimation(fig, update_combined,
                                        frames=time_steps, interval=200, blit=False)

# Display and save GIF
plt.show()
combined_anim.save('density_correlation_overlay.gif', writer='pillow', fps=5)


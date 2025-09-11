# Full updated script — continue from imports...
import networkx as nx
import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib as mpl
import random
import matplotlib.animation as animation
import scipy.sparse as sp
import datetime

# ----------- Parameters -------------
num_nodes = 20
avg_degree = 3
r_max = 20
sample_size = 5

time_steps = 50
tau = 10.0
dt = 1.0
sigma = 5.0
minor_road_prob = 0.7
x_nearest = 3

capacity_per_edge = 20
rho_max = 100
k = 0.5
sink_capacity = 60  # NEW: Limit on per-timestep sink inflow

# ----------- Create Graph ------------

G = nx.DiGraph()

node_types = {}
sources = random.sample(range(num_nodes), k=int(0.05 * num_nodes))
remaining_nodes = set(range(num_nodes)) - set(sources)
sinks = random.sample(list(remaining_nodes), k=int(0.05 * num_nodes))
internals = list(set(range(num_nodes)) - set(sources) - set(sinks))

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
        external_flow[i] = -random.randint(15, 50)
    else:
        external_flow[i] = 0

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

grid_size = int(np.ceil(np.sqrt(num_nodes)))
positions = {}
for i in range(num_nodes):
    x = i % grid_size
    y = i // grid_size
    positions[i] = (x, y)

# --- Edge creation with no sink-to-sink edges
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

def segments_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])
    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))

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

# --- Ensure all nodes can reach at least one sink ---
def ensure_connectivity_to_sink(G, sinks, positions):
    for node in G.nodes():
        if G.nodes[node]['node_type'] == 'sink':
            continue
        can_reach_sink = any(nx.has_path(G, node, sink) for sink in sinks)
        if not can_reach_sink:
            candidates = [n for n in G.nodes() if n != node and n not in sinks]
            candidates = sorted(candidates, key=lambda n: np.linalg.norm(np.array(positions[n]) - np.array(positions[node])))
            for target in candidates:
                if any(nx.has_path(G, target, sink) for sink in sinks):
                    G.add_edge(node, target)
                    break

ensure_connectivity_to_sink(G, sinks, positions)

# ----------- Vectorized density evolution ------------

num_nodes = G.number_of_nodes()
rho_current = np.array([G.nodes[i]['inflow'] for i in range(num_nodes)], dtype=float)
rho_current = np.clip(rho_current, 0, rho_max)
S = np.array([G.nodes[i]['S'] for i in range(num_nodes)], dtype=float)

A_out = nx.adjacency_matrix(G, nodelist=range(num_nodes)).tocsc()
A_in = A_out.transpose().tocsc()

# --- Compute proximity to sinks ---
sink_set = set(sinks)
sink_distances = np.full(num_nodes, np.inf)
for i in range(num_nodes):
    lengths = nx.single_source_shortest_path_length(G, i)
    min_dist = min([lengths.get(s, np.inf) for s in sink_set])
    sink_distances[i] = min_dist

finite_sink_distances = np.where(np.isinf(sink_distances), 2 * num_nodes, sink_distances)
sink_proximity = (finite_sink_distances.max() - finite_sink_distances) / finite_sink_distances.max()

rho_t_list = []
delta_t_list = []

for step in range(time_steps):
    congestion = 1 - rho_current / rho_max

    rows_in, cols_in = A_in.nonzero()
    data_in = k * rho_current[cols_in] * congestion[rows_in]
    data_in = np.clip(data_in, 0, capacity_per_edge)
    F_in = sp.coo_matrix((data_in, (rows_in, cols_in)), shape=A_in.shape).tocsc()
    inflow = np.array(F_in.sum(axis=1)).flatten()
    # Cap inflow at sinks
    for sink in sinks:
        inflow_from_neighbors = 0.0
        for pred in G.predecessors(sink):
            edge_idx = G.edges[pred, sink]
            flow = k * rho_current[pred] * (1 - rho_current[sink]/rho_max)
            inflow_from_neighbors += min(flow, capacity_per_edge)
        inflow[sink] = min(inflow_from_neighbors, sink_capacity)


    rows_out, cols_out = A_out.nonzero()
    data_out = k * rho_current[rows_out] * congestion[cols_out]
    data_out = np.clip(data_out, 0, capacity_per_edge)
    F_out = sp.coo_matrix((data_out, (rows_out, cols_out)), shape=A_out.shape).tocsc()
    outflow = np.array(F_out.sum(axis=1)).flatten()

    rho_next = rho_current + dt * (inflow - outflow + S)
    rho_next = np.clip(rho_next, 0, rho_max)

    rho_t_list.append(rho_next)
    mean_rho = np.mean(rho_next)
    delta_next = (rho_next - mean_rho) / mean_rho
    delta_t_list.append(delta_next)

    rho_current = rho_next

# Remaining correlation and plotting code here...

# ---------------- Existing simulation loop (your code) ----------------

# (Note: original script included a duplicated loop — keeping the subsequent one as the script did.)
rho_t_list = []
delta_t_list = []

for step in range(time_steps):
    congestion = 1 - rho_current / rho_max

    rows_in, cols_in = A_in.nonzero()
    data_in = k * rho_current[cols_in] * congestion[rows_in]
    data_in = np.clip(data_in, 0, capacity_per_edge)
    F_in = sp.coo_matrix((data_in, (rows_in, cols_in)), shape=A_in.shape).tocsc()
    inflow = np.array(F_in.sum(axis=1)).flatten()
    for sink in sinks:
        inflow[sink] = min(inflow[sink], sink_capacity)

    rows_out, cols_out = A_out.nonzero()
    data_out = k * rho_current[rows_out] * congestion[cols_out]
    data_out = np.clip(data_out, 0, capacity_per_edge)
    F_out = sp.coo_matrix((data_out, (rows_out, cols_out)), shape=A_out.shape).tocsc()
    outflow = np.array(F_out.sum(axis=1)).flatten()

    rho_next = rho_current + dt * (inflow - outflow + S)
    rho_next = np.clip(rho_next, 0, rho_max)

    rho_t_list.append(rho_next)
    mean_rho = np.mean(rho_next)
    delta_next = (rho_next - mean_rho) / mean_rho
    delta_t_list.append(delta_next)

    rho_current = rho_next

# --- New Animation: Node network with adjacent correlation color map ---

fig_corr_net, ax_corr_net = plt.subplots(figsize=(10, 10))
ax_corr_net.set_title("Nodal Network Colored by Adjacent Correlation Over Time")
ax_corr_net.axis("off")

# Compute color limits for consistency across frames
all_corr_vals = []
for delta in delta_t_list:
    corr_vals = []
    for i in G.nodes:
        neighbors = list(G.successors(i)) + list(G.predecessors(i))
        corrs = [delta[i] * delta[nn] for nn in neighbors]
        if corrs:
            corr_vals.append(np.mean(corrs))
    all_corr_vals.extend(corr_vals)

min_corr, max_corr = min(all_corr_vals), max(all_corr_vals)
norm_corr = mpl.colors.Normalize(vmin=min_corr, vmax=max_corr)
cmap_corr = plt.cm.coolwarm
sm_corr = plt.cm.ScalarMappable(norm=norm_corr, cmap=cmap_corr)
plt.colorbar(sm_corr, ax=ax_corr_net, label="Average Correlation with Neighbors")

# Static underlying network (edges as roads)
nx.draw_networkx_edges(G, positions, edge_color='lightgray', width=0.8, alpha=0.5, ax=ax_corr_net)

# Initial node coloring
initial_delta = delta_t_list[0]
initial_corrs = []
for i in G.nodes:
    neighbors = list(G.successors(i)) + list(G.predecessors(i))
    corrs = [initial_delta[i] * initial_delta[nn] for nn in neighbors]
    avg_corr = np.mean(corrs) if corrs else 0
    initial_corrs.append(avg_corr)

nodes_corr_plot = nx.draw_networkx_nodes(
    G, positions,
    node_color=initial_corrs,
    cmap=cmap_corr,
    node_size=60,
    ax=ax_corr_net
)

def update_corr_network(frame):
    delta = delta_t_list[frame]
    node_colors = []
    for i in G.nodes:
        neighbors = list(G.successors(i)) + list(G.predecessors(i))
        corrs = [delta[i] * delta[nn] for nn in neighbors]
        avg_corr = np.mean(corrs) if corrs else 0
        node_colors.append(avg_corr)

    nodes_corr_plot.set_array(np.array(node_colors))
    ax_corr_net.set_title(f"Avg Adjacent Correlation - Timestep {frame+1}/{time_steps}")
    return nodes_corr_plot,

# Create the animation
adj_corr_anim = animation.FuncAnimation(
    fig_corr_net, update_corr_network,
    frames=time_steps, interval=100, blit=True
)


# ---------------- 🆕 NEW: Dynamical average correlation over adjacent nodes ----------------

total_corr = 0
edge_count = 0
edge_corr_over_time = defaultdict(list)

for t in range(time_steps):
    delta = delta_t_list[t]
    for (u, v) in G.edges():
        corr = delta[u] * delta[v]
        total_corr += corr
        edge_corr_over_time[(u, v)].append(corr)
        edge_count += 1

dynamical_avg_corr = total_corr / edge_count if edge_count > 0 else 0

print(f"\n✅ Dynamical average correlation over adjacent nodes: {dynamical_avg_corr:.4f}\n")

# Compute time-averaged correlation per edge
avg_edge_corr = {edge: np.mean(vals) for edge, vals in edge_corr_over_time.items()}

# ---------------- 🆕 NEW: Histogram of average edge correlations ----------------

plt.figure(figsize=(6, 4))
plt.hist(avg_edge_corr.values(), bins=30, color='skyblue', edgecolor='black')
plt.title("Histogram of Average Edge Correlations Over Time")
plt.xlabel("Average Correlation (δᵢ * δⱼ)")
plt.ylabel("Number of Edges")
plt.grid(True)
plt.tight_layout()
plt.show()

# ------------------ 🖼️ Visualize Network with Colored Edges ------------------

fig, ax = plt.subplots(figsize=(10, 10))
ax.set_title("Network Colored by Average Correlation of Adjacent Nodes")
ax.axis('off')

# Get edge list and their average correlation values
edges = list(avg_edge_corr.keys())
corr_values = list(avg_edge_corr.values())

# Normalize for colormap
norm = mpl.colors.Normalize(vmin=min(corr_values), vmax=max(corr_values))
cmap = plt.cm.plasma
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)

# Draw edges with color mapping
nx.draw_networkx_edges(
    G, positions,
    edgelist=edges,
    edge_color=[cmap(norm(val)) for val in corr_values],
    width=1.5,
    alpha=0.9,
    ax=ax
)

# Draw nodes in gray
nx.draw_networkx_nodes(G, positions, node_color='gray', node_size=50, ax=ax)

# Colorbar
cbar = plt.colorbar(sm, ax=ax)
cbar.set_label("Average Edge Correlation (δᵢ ⋅ δⱼ) over Time")

plt.tight_layout()
plt.show()


# --- Compute two-point correlation function ---

def compute_two_point_correlation(G, delta_t, r_max):
    sum_corr = defaultdict(float)
    count_corr = defaultdict(int)
    for i in G.nodes:
        lengths = nx.single_source_shortest_path_length(G, i, cutoff=r_max)
        for j, dist in lengths.items():
            if i != j:
                sum_corr[dist] += delta_t[i] * delta_t[j]
                count_corr[dist] += 1
    distances = sorted(sum_corr.keys())
    xi_r = [sum_corr[d] / count_corr[d] for d in distances]
    return distances, xi_r

# --- Compute nearest neighbors ---

def get_x_nearest_neighbors(G, x):
    nearest_dict = {}
    for node in G.nodes:
        lengths = nx.single_source_shortest_path_length(G, node)
        filtered = sorted([(n, d) for n, d in lengths.items() if n != node], key=lambda x: x[1])
        nearest_nodes = [n for n, d in filtered[:x]]
        nearest_dict[node] = nearest_nodes
    return nearest_dict

nearest_neighbors = get_x_nearest_neighbors(G, x_nearest)

# --- Compute average correlation over x nearest neighbors at each timestep ---

avg_corr_x_nearest = []
for t in range(time_steps):
    dt_arr = delta_t_list[t]
    corrs = []
    for i in G.nodes:
        for nn in nearest_neighbors[i]:
            corrs.append(dt_arr[i] * dt_arr[nn])
    avg_corr_x_nearest.append(np.mean(corrs) if corrs else 0)

# --- Compute max correlation and distance per timestep ---

max_corr_per_timestep = []
max_corr_dist_per_timestep = []

for t in range(time_steps):
    distances, xi_r = compute_two_point_correlation(G, delta_t_list[t], r_max)
    if xi_r:
        max_val = max(xi_r)
        max_idx = xi_r.index(max_val)
        max_dist = distances[max_idx]
    else:
        max_val = 0
        max_dist = 0
    max_corr_per_timestep.append(max_val)
    max_corr_dist_per_timestep.append(max_dist)

# --- Animation 1: Two-point correlation function over time ---

fig1, ax1 = plt.subplots(figsize=(6,4))
line, = ax1.plot([], [], marker='o', linestyle='-')
marker, = ax1.plot([], [], marker='*', color='red', markersize=15, label='Max Correlation')
ax1.set_xlabel("Graph Distance r")
ax1.set_ylabel(r"Two-Point Correlation $\xi(r)$")
ax1.set_title("Two-Point Correlation Function Over Time")
ax1.grid(True)
ax1.legend()

def init():
    ax1.set_xlim(1, r_max)
    ax1.set_ylim(-1, 1)
    line.set_data([], [])
    marker.set_data([], [])
    return line, marker

def update_corr(frame):
    distances, xi_r = compute_two_point_correlation(G, delta_t_list[frame], r_max)
    line.set_data(distances, xi_r)
    if xi_r:
        max_val = max_corr_per_timestep[frame]
        max_dist = max_corr_dist_per_timestep[frame]
        marker.set_data([max_dist], [max_val])
    else:
        marker.set_data([], [])
    ax1.set_title(f"Two-Point Correlation at timestep {frame+1}/{time_steps}")
    return line, marker

ani1 = animation.FuncAnimation(fig1, update_corr, frames=time_steps, init_func=init, blit=True, interval=100)

# --- Animation 2: Node color evolution of δ_i(t) ---

fig2, ax2 = plt.subplots(figsize=(8, 8))
ax2.set_title('Density Contrast δ_i(t) over Time')
ax2.axis('off')

max_abs_delta = max(np.max(np.abs(delta_t_list)), np.abs(np.min(np.array(delta_t_list))))
norm = plt.Normalize(vmin=-max_abs_delta, vmax=max_abs_delta)
cmap = plt.cm.coolwarm

node_colors = [cmap(norm(delta_t_list[0][node])) for node in G.nodes()]
nodes = nx.draw_networkx_nodes(G, positions, node_color=node_colors, node_size=80, ax=ax2)
edges = nx.draw_networkx_edges(G, positions, alpha=0.3, ax=ax2)

def update_delta(frame):
    current_delta = delta_t_list[frame]
    new_colors = [cmap(norm(current_delta[node])) for node in G.nodes()]
    nodes.set_color(new_colors)
    ax2.set_title(f'Density Contrast δ_i(t) at timestep {frame+1}/{time_steps}')
    return nodes,

ani2 = animation.FuncAnimation(fig2, update_delta, frames=time_steps, interval=100, blit=True)

# --- Plot Subgraph induced by edges with positive correlation at final timestep ---

delta_final = delta_t_list[-1]
pos_edges = []
for (u, v) in G.edges():
    if delta_final[u] * delta_final[v] > 0:
        pos_edges.append((u, v))
G_sub = G.edge_subgraph(pos_edges).copy()

plt.figure(figsize=(10,10))
plt.title("Subgraph of edges with positive correlation (final timestep)")
plt.axis('off')
nx.draw_networkx_nodes(G_sub, positions, node_size=50)
nx.draw_networkx_edges(G_sub, positions, alpha=0.5)


# --- Compute average correlation with x nearest neighbors at final timestep ---

avg_corr = []
for i in G.nodes:
    neighbors = nearest_neighbors[i]
    corrs = [delta_final[i] * delta_final[nn] for nn in neighbors]
    avg_corr.append(np.mean(corrs) if corrs else 0)

# --- Final Plot: Nodal network colored by average correlation ---

def compute_positive_edge_correlations(G, delta_t):
    edge_corrs = {}
    for (u, v) in G.edges():
        corr = delta_t[u] * delta_t[v]
        if corr > 0:
            edge_corrs[(u, v)] = corr
    return edge_corrs

fig, ax = plt.subplots(figsize=(10, 10))
ax.set_title("Animated Edge Correlations Over Time")
ax.axis('off')

# Static nodes
nodes_drawn = nx.draw_networkx_nodes(G, positions, node_size=40, node_color='gray', ax=ax)
edges_collection = []

# Initial color normalization setup
edge_corrs_initial = compute_positive_edge_correlations(G, delta_t_list[0])
edge_corr_values = list(edge_corrs_initial.values()) if edge_corrs_initial else [0, 1]
norm = mpl.colors.Normalize(vmin=min(edge_corr_values), vmax=max(edge_corr_values))
cmap = plt.cm.plasma

sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
cbar = plt.colorbar(sm, ax=ax)
cbar.set_label("Edge Correlation Value")

def init_anim():
    global edges_collection
    edges_collection = []
    return []

def update_anim(frame):
    global edges_collection
    for artist in edges_collection:
        artist.remove()
    edges_collection = []

    delta = delta_t_list[frame]
    edge_corrs = compute_positive_edge_correlations(G, delta)

    if edge_corrs:
        edge_corr_values = list(edge_corrs.values())
        norm = mpl.colors.Normalize(vmin=min(edge_corr_values), vmax=max(edge_corr_values))

        for (u, v), val in edge_corrs.items():
            color = cmap(norm(val))
            edge = nx.draw_networkx_edges(
                G, positions,
                edgelist=[(u, v)],
                width=1.5,
                edge_color=[color],
                alpha=norm(val),  # transparency reflects correlation strength
                ax=ax
            )
            edges_collection.extend(edge)

    ax.set_title(f"Edge Correlation Network - Timestep {frame + 1}/{time_steps}")
    return edges_collection

edge_corr_anim = animation.FuncAnimation(
    fig, update_anim, init_func=init_anim,
    frames=time_steps, interval=100, blit=False
)


# ================== 🆕 Combined Node + Edge Correlation Animation (integrated) ==================

fig_combined, ax_combined = plt.subplots(figsize=(10, 10))
ax_combined.set_title("Combined Node + Edge Correlation Network Over Time")
ax_combined.axis('off')

# Precompute node correlation range
all_node_corr_vals = []
for delta in delta_t_list:
    for i in G.nodes:
        nbs = list(G.successors(i)) + list(G.predecessors(i))
        corrs = [delta[i] * delta[nn] for nn in nbs]
        if corrs:
            all_node_corr_vals.append(np.mean(corrs))

# If for some reason there are no node corr vals (rare), provide small default bounds
if len(all_node_corr_vals) == 0:
    all_node_corr_vals = [0.0, 1.0]

norm_nodes = mpl.colors.Normalize(vmin=min(all_node_corr_vals),
                                  vmax=max(all_node_corr_vals))
cmap_nodes = plt.cm.coolwarm

# Initial node colours
delta0 = delta_t_list[0]
node_corr0 = []
for i in G.nodes:
    nbs = list(G.successors(i)) + list(G.predecessors(i))
    corrs = [delta0[i] * delta0[nn] for nn in nbs]
    node_corr0.append(np.mean(corrs) if corrs else 0)

nodes_artist = nx.draw_networkx_nodes(
    G, positions,
    node_color=[cmap_nodes(norm_nodes(val)) for val in node_corr0],
    node_size=60, ax=ax_combined, alpha=0.8
)

edge_artists = []

sm_nodes = plt.cm.ScalarMappable(norm=norm_nodes, cmap=cmap_nodes)
cbar_nodes = plt.colorbar(sm_nodes, ax=ax_combined, fraction=0.046, pad=0.04)
cbar_nodes.set_label("Node Avg Correlation with Neighbors")

sm_edges = plt.cm.ScalarMappable(cmap=plt.cm.plasma)
cbar_edges = plt.colorbar(sm_edges, ax=ax_combined, fraction=0.046, pad=0.04)
cbar_edges.set_label("Edge Correlation Value")

def update_combined(frame):
    delta = delta_t_list[frame]

    # Update node colours
    node_corr = []
    for i in G.nodes:
        nbs = list(G.successors(i)) + list(G.predecessors(i))
        corrs = [delta[i] * delta[nn] for nn in nbs]
        node_corr.append(np.mean(corrs) if corrs else 0)
    # set_color can accept a list of RGBA or hex; we use the cmap to create colors
    nodes_artist.set_color([cmap_nodes(norm_nodes(val)) for val in node_corr])

    # Update edges
    for artist in edge_artists:
        try:
            artist.remove()
        except Exception:
            pass
    edge_artists.clear()

    edge_corrs = compute_positive_edge_correlations(G, delta)
    if edge_corrs:
        edge_corr_values = list(edge_corrs.values())
        # Provide a fallback if edge_corr_values are constant
        vmin = min(edge_corr_values) if len(edge_corr_values) > 0 else 0
        vmax = max(edge_corr_values) if len(edge_corr_values) > 0 else 1
        norm_edges = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
        for (u, v), val in edge_corrs.items():
            color = plt.cm.plasma(norm_edges(val))
            e = nx.draw_networkx_edges(
                G, positions, edgelist=[(u, v)],
                width=1.5, edge_color=[color],
                alpha=0.6, ax=ax_combined
            )
            edge_artists.extend(e)

    ax_combined.set_title(f"Node+Edge Correlation - Timestep {frame+1}/{time_steps}")
    return [nodes_artist] + edge_artists

combined_anim = animation.FuncAnimation(
    fig_combined, update_combined,
    frames=time_steps, interval=100, blit=False
)


# ------------------ 🆕 Save animations as GIFs ------------------

# create filenames with timestamps to avoid overwriting
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
filenames = {
    'adj_corr': f"adjacent_node_correlation_{ts}.gif",
    'two_point': f"two_point_correlation_{ts}.gif",
    'delta_evolution': f"delta_evolution_{ts}.gif",
    'edge_corr': f"edge_correlation_{ts}.gif",
    'combined': f"combined_network_{ts}.gif"
}

# Helper function to save safely
def try_save(anim, fname, fps=10):
    try:
        anim.save(fname, writer='pillow', fps=fps)
        print(f"Saved animation to {fname}")
    except Exception as e:
        print(f"Could not save {fname}: {e}. Make sure pillow is installed (pip install pillow).")

# Save animations (if they exist)
try_save(adj_corr_anim, filenames['adj_corr'], fps=10)
try_save(ani1, filenames['two_point'], fps=10)
try_save(ani2, filenames['delta_evolution'], fps=10)
try_save(edge_corr_anim, filenames['edge_corr'], fps=10)
try_save(combined_anim, filenames['combined'], fps=10)

# Finally show plots (blocking)
plt.show()

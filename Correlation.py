import networkx as nx
import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib as mpl
import random
import matplotlib.animation as animation

# ----------- Parameters -------------
num_nodes = 100
avg_degree = 4
r_max = 10
sample_size = 100

time_steps = 100
tau = 10.0
dt = 1.0
sigma = 5.0
minor_road_prob = 0.5
x_nearest = 3  # number of nearest neighbors to average correlation over

# ----------- Create Graph ------------

G = nx.DiGraph()

# Assign node types randomly (5% sources, 5% sinks, rest internal)
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

# Assign external flow S_i
external_flow = {}
for i in range(num_nodes):
    if node_types[i] == 'source':
        external_flow[i] = random.randint(15, 50)   # inflow
    elif node_types[i] == 'sink':
        external_flow[i] = -random.randint(15, 50)  # outflow
    else:
        external_flow[i] = 0

# Add nodes with attributes
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

# Assign positions on a grid to simulate city layout
grid_size = int(np.ceil(np.sqrt(num_nodes)))
positions = {}
for i in range(num_nodes):
    x = i % grid_size
    y = i // grid_size
    # Add a small random noise to positions to avoid perfect grid alignment
    positions[i] = (x + 0.1 * random.uniform(-0.5, 0.5), y + 0.1 * random.uniform(-0.5, 0.5))

# Create edges with preference:
# - no edges source->source (to separate housing estates)
# - edges preferentially towards sinks (simulate main roads)
# - internal nodes have bidirectional edges (2-way streets)
for i in range(num_nodes):
    targets = set()
    while len(targets) < avg_degree:
        t = random.randint(0, num_nodes - 1)
        if t == i:
            continue
        # No source to source edges
        if node_types[i] == 'source' and node_types[t] == 'source':
            continue
        # Preference to connect to sinks with higher probability
        if node_types[t] == 'sink':
            prob = 0.7
        else:
            prob = 0.3
        if random.random() > prob:
            continue
        targets.add(t)
    for t in targets:
        G.add_edge(i, t)
        # For internal nodes, add reverse edge for 2-way streets
        if node_types[i] == 'internal' and node_types[t] == 'internal':
            G.add_edge(t, i)

# --------- Edge crossing detection & minor road replacement ---------

def segments_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1]-a[1])*(b[0]-a[0]) > (b[1]-a[1])*(c[0]-a[0])
    return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))

def remove_edge_crossings_and_add_minor_roads(G, positions, minor_road_prob=0.5):
    edges = list(G.edges())
    crossing_edges = set()

    # Step 1: Detect all crossing edges
    for i in range(len(edges)):
        u1, v1 = edges[i]
        p1, p2 = positions[u1], positions[v1]
        for j in range(i + 1, len(edges)):
            u2, v2 = edges[j]
            if len({u1, v1, u2, v2}) < 4:
                # Skip edges sharing a node
                continue
            p3, p4 = positions[u2], positions[v2]
            if segments_intersect(p1, p2, p3, p4):
                crossing_edges.add((u1, v1))
                crossing_edges.add((u2, v2))

    print(f"Found {len(crossing_edges)} edges involved in crossings.")

    # Step 2: Remove all crossing edges
    for e in crossing_edges:
        if G.has_edge(*e):
            G.remove_edge(*e)

    print(f"Removed {len(crossing_edges)} crossing edges.")

    # Step 3: Attempt to add minor roads without creating new crossings
    added_minor_roads = []

    # Candidate pairs to try minor roads: pairs of nodes close to each other, not connected already
    node_list = list(G.nodes())
    for i in node_list:
        for j in node_list:
            if i == j:
                continue
            if G.has_edge(i, j):
                continue
            # Only add minor roads between nodes closer than threshold
            dist = np.linalg.norm(np.array(positions[i]) - np.array(positions[j]))
            if dist > 1.5:
                continue
            # Probability check
            if random.random() > minor_road_prob:
                continue
            # Check if adding edge i->j or j->i causes crossings
            can_add_ij = True
            can_add_ji = True
            for (u, v) in G.edges():
                # Skip if sharing node
                if len({i, j, u, v}) < 4:
                    continue
                if segments_intersect(positions[i], positions[j], positions[u], positions[v]):
                    can_add_ij = False
                if segments_intersect(positions[j], positions[i], positions[u], positions[v]):
                    can_add_ji = False
                if not can_add_ij and not can_add_ji:
                    break
            # Add minor roads if no crossing results and nodes are not sinks
            if can_add_ij and G.nodes[i]['node_type'] != 'sink' and G.nodes[j]['node_type'] != 'sink':
                G.add_edge(i, j)
                added_minor_roads.append((i, j))
            if can_add_ji and G.nodes[j]['node_type'] != 'sink' and G.nodes[i]['node_type'] != 'sink':
                G.add_edge(j, i)
                added_minor_roads.append((j, i))

    print(f"Added {len(added_minor_roads)} minor road edges without causing crossings.")

remove_edge_crossings_and_add_minor_roads(G, positions, minor_road_prob=minor_road_prob)

# ----------- Compute density contrast δ_i --------------

rho = np.array([G.nodes[i]['inflow'] for i in G.nodes])
mean_rho = np.mean(rho)
delta = (rho - mean_rho) / mean_rho

# ----------- Time-dependent evolution of δ_i -------------

delta_t_list = []
delta_current = delta.copy()

for step in range(time_steps):
    delta_next = delta_current + (dt / tau) * (-delta_current + sigma * np.random.randn(num_nodes))
    delta_t_list.append(delta_next)
    delta_current = delta_next

# --- Calculate two-point correlation function for animation ---

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

# --- Compute nearest neighbors for each node up to x_nearest ---

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

# --- Compute max correlation value and distance at each timestep ---

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

# --- Animation 1: Two-point correlation function over time with max correlation marker ---

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
plt.show()

# --- Compute average correlation with x nearest neighbors at final timestep ---

avg_corr = []
for i in G.nodes:
    neighbors = nearest_neighbors[i]
    corrs = [delta_final[i] * delta_final[nn] for nn in neighbors]
    avg_corr.append(np.mean(corrs) if corrs else 0)

# --- Final Plot: Nodal network colored by average correlation instead of bar chart ---

fig, ax = plt.subplots(figsize=(10, 10))
ax.set_title(f'Average correlation with {x_nearest} nearest neighbors at final timestep')
ax.axis('off')

avg_corr_values = np.array(avg_corr)
norm_corr = mpl.colors.Normalize(vmin=np.min(avg_corr_values), vmax=np.max(avg_corr_values))
cmap = plt.cm.viridis

nodes = nx.draw_networkx_nodes(
    G, positions,
    node_color=avg_corr_values,
    cmap=cmap,
    node_size=100,
    ax=ax
)
nx.draw_networkx_edges(G, positions, alpha=0.3, ax=ax)

sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm_corr)
sm.set_array(avg_corr_values)
fig.colorbar(sm, ax=ax, label='Average correlation')

plt.show()

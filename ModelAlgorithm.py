import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx

N_sources = 10
N_roads = 15
N_sinks = 3
beta = 1.0
a = 0.3
sink_rate = 0.2
T = 200

rng = np.random.default_rng(1)

R_sources = np.random.randint(40, 60, size=N_sources)
total_sources_cap = int(R_sources.sum())

w = rng.random(N_sinks) + 0.1
raw = w / w.sum() * total_sources_cap
R_sinks = np.floor(raw).astype(int)
remainder = total_sources_cap - R_sinks.sum()
order = np.argsort(raw - R_sinks)[::-1]
for k in order[:remainder]:
    R_sinks[k] += 1

R_roads = np.random.randint(20, 40, size=N_roads)

r_sources = R_sources.copy().astype(float)
r_roads = np.zeros(N_roads, dtype=float)
r_sinks = np.zeros(N_sinks, dtype=float)

tau = np.random.rand(N_roads, N_sinks) * 5.0

neighbors = (rng.random((N_roads, N_roads)) < 0.3).astype(int)
np.fill_diagonal(neighbors, 0)

G = nx.DiGraph()
for i in range(N_sources):
    G.add_node(f"H{i}", type="source")
for i in range(N_roads):
    G.add_node(f"R{i}", type="road")
for j in range(N_sinks):
    G.add_node(f"S{j}", type="sink")

for i in range(N_sources):
    k = rng.integers(1, min(3, N_roads) + 1)
    choices = rng.choice(N_roads, size=k, replace=False)
    for rr in choices:
        G.add_edge(f"H{i}", f"R{rr}")

for i in range(N_roads):
    for j in range(N_roads):
        if neighbors[i, j]:
            G.add_edge(f"R{i}", f"R{j}")

for i in range(N_roads):
    connected = False
    for j in range(N_sinks):
        if rng.random() < 0.5:
            G.add_edge(f"R{i}", f"S{j}")
            connected = True
    if not connected:
        j = rng.integers(0, N_sinks)
        G.add_edge(f"R{i}", f"S{j}")

pos = {}
for i in range(N_sources):
    pos[f"H{i}"] = (-2.6, i - (N_sources - 1) / 2)

angles = np.linspace(0, 2*np.pi, N_roads, endpoint=False)
radius = 2.0
for i in range(N_roads):
    x = np.cos(angles[i]) * radius * 0.6
    y = np.sin(angles[i]) * radius
    pos[f"R{i}"] = (0 + x, y * 0.6)

for j in range(N_sinks):
    pos[f"S{j}"] = (2.8, j - (N_sinks - 1) / 2)

def capacity_left_all():
    return np.maximum(R_sinks - r_sinks, 0.0)

def dynamic_importance_all():
    cap_left = capacity_left_all()
    tot = cap_left.sum()
    if tot <= 0:
        return np.ones_like(cap_left) / len(cap_left)
    return cap_left / tot

def update_step(r_sources, r_roads, r_sinks):
    for i in range(N_sources):
        succ = [n for n in G.successors(f"H{i}") if n.startswith("R")]
        if len(succ) == 0:
            continue
        amount = min(r_sources[i], 2.0)
        if amount > 0:
            share = amount / len(succ)
            for nbr in succ:
                idx = int(nbr[1:])
                r_roads[idx] += share
            r_sources[i] -= amount

    imp_all = dynamic_importance_all()
    Δtau = tau[:, None, :] - tau[None, :, :]
    Δtau = Δtau * neighbors[:, :, None]
    f = np.exp(-beta * Δtau) * imp_all[None, None, :]
    Z = f.sum(axis=(1, 2)) + 1e-12
    P = f / Z[:, None, None]

    rho = r_roads / R_roads
    stay = a * rho * r_roads
    distribute_mass = r_roads - stay
    flow = distribute_mass[:, None, None] * P

    inflow_roads = flow.sum(axis=(0, 2))
    r_roads_new = stay + inflow_roads

    for i in range(N_roads):
        succ_sinks = [n for n in G.successors(f"R{i}") if n.startswith("S")]
        if len(succ_sinks) == 0:
            continue
        J = np.array([int(s[1:]) for s in succ_sinks], dtype=int)
        cap_left = np.maximum(R_sinks[J] - r_sinks[J], 0.0)
        if cap_left.sum() <= 0:
            continue
        w = cap_left * np.exp(-beta * tau[i, J])
        if w.sum() <= 0:
            continue
        remaining = sink_rate * r_roads_new[i]
        sends = np.zeros_like(cap_left)
        mask = cap_left > 1e-12
        W = w.copy()
        while remaining > 1e-12 and mask.any():
            q = np.zeros_like(W)
            q[mask] = W[mask] / W[mask].sum()
            alloc = remaining * q
            take = np.minimum(alloc, cap_left - sends)
            got = take.sum()
            if got <= 1e-12:
                break
            sends += take
            remaining -= got
            mask = (cap_left - sends) > 1e-12
            W[~mask] = 0.0
        r_roads_new[i] -= sends.sum()
        r_sinks[J] += sends

    return r_sources, r_roads_new, r_sinks

fig, ax = plt.subplots(figsize=(8, 6))
cmap = plt.cm.plasma_r

def get_colors(r, R):
    rho = r / R
    rho_clip = np.clip(rho, 0, 1)
    return cmap(rho_clip)

def draw_percent_labels(ax, pos, r_sources, r_roads, r_sinks):
    for node, (x, y) in pos.items():
        if node.startswith("H"):
            idx = int(node[1:])
            pct = 100.0 * (r_sources[idx] / R_sources[idx])
        elif node.startswith("R"):
            idx = int(node[1:])
            pct = 100.0 * (r_roads[idx] / R_roads[idx])
        else:
            idx = int(node[1:])
            pct = 100.0 * (r_sinks[idx] / R_sinks[idx])
        ax.text(x, y - 0.35, f"{pct:.1f}%", ha="center", va="center", fontsize=9, color="black")

def animate(t):
    global r_sources, r_roads, r_sinks
    ax.clear()
    r_sources, r_roads, r_sinks = update_step(r_sources, r_roads, r_sinks)

    node_colors = []
    for node in G.nodes():
        if G.nodes[node]['type'] == 'source':
            idx = int(node[1:])
            node_colors.append(get_colors(np.array([r_sources[idx]]), np.array([R_sources[idx]]))[0])
        elif G.nodes[node]['type'] == 'road':
            idx = int(node[1:])
            node_colors.append(get_colors(np.array([r_roads[idx]]), np.array([R_roads[idx]]))[0])
        else:
            idx = int(node[1:])
            node_colors.append(get_colors(np.array([r_sinks[idx]]), np.array([R_sinks[idx]]))[0])

    nx.draw(G, pos, with_labels=True, ax=ax,
            node_color=node_colors, node_size=650,
            font_color="white", arrows=False)
    draw_percent_labels(ax, pos, r_sources, r_roads, r_sinks)
    ax.set_title(f"Traffic distribution with dynamic sink importance (t={t})")
    ax.set_axis_off()

ani = animation.FuncAnimation(fig, animate, frames=T, interval=200, repeat=False)
plt.show()

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx
import itertools
import heapq

# ---------- parameters ----------
N_sources = 4
N_roads   = 10
N_sinks   = 5

beta = 1.0
a    = 0.3
sink_rate = 0.20
INTERVAL_MS = 200
c_cost = 2
rng = np.random.default_rng(17)
EPS = 1e-12
INF = 1e18
BIG = 1e12

T_SECOND = 0.30  # fraction of each road's outflow that intentionally takes the 2nd-best neighbor

# Smoother flow controls
MOVE_RATE_NORMAL = 0.90
MOVE_RATE_DRAIN  = 0.70
FINAL_STAY       = 0.10
FINAL_SINK_RATE  = 0.12
FINAL_STEPS_PER_FRAME = 2
DRAIN_TOL = 1e-9

# ---------- capacities (match total people to total sink capacity) ----------
R_sources = np.random.randint(40, 60, size=N_sources).astype(float)
TOTAL0 = float(R_sources.sum())

wtmp = rng.random(N_sinks) + 0.1
raw  = wtmp / wtmp.sum() * TOTAL0
R_sinks = np.floor(raw).astype(float)
rem = int(round(TOTAL0 - R_sinks.sum()))
if rem > 0:
    order = np.argsort(raw - R_sinks)[::-1]
    for k in order[:rem]: R_sinks[k] += 1.0
elif rem < 0:
    order = np.argsort(R_sinks - raw)[::-1]
    for k in order[:(-rem)]: R_sinks[k] -= 1.0

R_roads = np.random.randint(5, 40, size=N_roads).astype(float)

# ---------- efficiencies & node-entry weights (roads) ----------
e_roads = rng.uniform(0.1, 5, size=N_roads)
w_roads = c_cost * R_roads * e_roads
w_sources = np.zeros(N_sources)
w_sinks   = np.zeros(N_sinks)

# ---------- occupancies ----------
r_sources = R_sources.copy()
r_roads   = np.zeros(N_roads, dtype=float)
r_sinks   = np.zeros(N_sinks, dtype=float)
r_roads_draw = r_roads.copy()  # pre-absorption visual

# ---------- road-road adjacency ----------
neighbors = (rng.random((N_roads, N_roads)) < 0.35).astype(int)
np.fill_diagonal(neighbors, 0)

# ---------- graph ----------
G = nx.DiGraph()
for i in range(N_sources): G.add_node(f"H{i}", type="source")
for i in range(N_roads):   G.add_node(f"R{i}", type="road")
for j in range(N_sinks):   G.add_node(f"S{j}", type="sink")

# H->R
for i in range(N_sources):
    k = rng.integers(1, min(3, N_roads) + 1)
    choices = rng.choice(N_roads, size=k, replace=False)
    for rr in choices:
        G.add_edge(f"H{i}", f"R{rr}")

# R->R
for i in range(N_roads):
    for j in range(N_roads):
        if neighbors[i, j]:
            G.add_edge(f"R{i}", f"R{j}")

# R->S (ensure each road reaches ≥1 sink)
for i in range(N_roads):
    connected = False
    for j in range(N_sinks):
        if rng.random() < 0.6:
            G.add_edge(f"R{i}", f"S{j}")
            connected = True
    if not connected:
        j = rng.integers(0, N_sinks)
        G.add_edge(f"R{i}", f"S{j}")

# ---------- layout ----------
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

# ---------- helpers ----------
def cap_left(arr_r, arr_R):
    return np.maximum(arr_R - arr_r, 0.0)

def attractiveness(curr_r, curr_R):
    # α = (capacity - occupancy)/capacity in [0,1]
    frac = 1.0 - np.divide(curr_r, curr_R, out=np.zeros_like(curr_r, float), where=curr_R!=0)
    return np.clip(frac, 0.0, 1.0)

def roads_that_can_reach_any_sink():
    has_RS = set(int(r[1:]) for j in range(N_sinks) for r in G.predecessors(f"S{j}") if r.startswith("R"))
    pred_roads_local = [np.flatnonzero(neighbors[:, n]).astype(int) for n in range(N_roads)]
    seen = set(has_RS)
    frontier = list(has_RS)
    while frontier:
        n = frontier.pop()
        for i in pred_roads_local[n]:
            if i not in seen:
                seen.add(i)
                frontier.append(i)
    return seen

# Ensure every road can reach a sink to avoid stranded mass
reachable = roads_that_can_reach_any_sink()
if len(reachable) < N_roads:
    j_best = int(np.argmax(R_sinks))
    for i in range(N_roads):
        if i not in reachable:
            G.add_edge(f"R{i}", f"S{j_best}")

# Pred lists / attachments (after any fixes)
pred_roads = [np.flatnonzero(neighbors[:, n]).astype(int) for n in range(N_roads)]
sink_to_roads = []
for j in range(N_sinks):
    rr = [int(r[1:]) for r in G.predecessors(f"S{j}") if r.startswith("R")]
    sink_to_roads.append(np.array(rr, dtype=int))
source_from_roads = []
for h in range(N_sources):
    rr = [int(r[1:]) for r in G.successors(f"H{h}") if r.startswith("R")]
    source_from_roads.append(np.array(rr, dtype=int))

# ---------- node-weighted shortest-path τ (roads -> sinks) ----------
def dijkstra_tau_to_sinks():
    tau = np.full((N_roads, N_sinks), INF, dtype=float)
    for j in range(N_sinks):
        dist = np.full(N_roads, INF, dtype=float)
        visited = np.zeros(N_roads, dtype=bool)
        pq = []
        heapq.heappush(pq, (0.0, ('S', j)))
        while pq:
            d, node = heapq.heappop(pq)
            typ = node[0]
            if typ == 'S':
                for i in sink_to_roads[j]:
                    if d < dist[i]:
                        dist[i] = d
                        heapq.heappush(pq, (dist[i], ('R', i)))
            else:
                n = node[1]
                if visited[n]: continue
                visited[n] = True
                w_edge = float(w_roads[n])      # entering n costs w_n
                for i in pred_roads[n]:         # reversed relax
                    nd = d + w_edge
                    if nd < dist[i]:
                        dist[i] = nd
                        heapq.heappush(pq, (nd, ('R', i)))
        dist[np.isinf(dist)] = BIG
        tau[:, j] = dist
    return tau

tau_S = dijkstra_tau_to_sinks()  # (N_roads, N_sinks)

# ---------- dynamics ----------
def inject_from_sources_forward():
    for i in range(N_sources):
        succ = [n for n in G.successors(f"H{i}") if n.startswith("R")]
        if not succ: continue
        amount = min(r_sources[i], 2.0)
        if amount > 0:
            share = amount / len(succ)
            for nbr in succ:
                idx = int(nbr[1:])
                r_roads[idx] += share
            r_sources[i] -= amount

def constrained_road_redistribution(tau_current, attr_vec, stay_factor, move_rate):
    """
    Two-route split with capacity caps:
      - For each i, compute S_{i,n} = sum_j exp(-β[τ[n,j]-τ[i,j]]) * α_j.
      - Pick n1 = argmax_n S_{i,n}, n2 = next best (if any).
      - Outflow out_i is split as: (1-T_SECOND) to n1, T_SECOND to n2.
      - Each share respects remaining capacity of its destination; any unsent remainder strands on i
        (or, if you prefer, you can optionally spill leftover of n1->n2 and n2->n1; see comments).
      - Guarantees r_pre[n] ≤ R_roads[n] (no overfill).
    """
    global r_roads, r_roads_draw

    # Retention & smoothing
    rho = np.divide(r_roads, R_roads, out=np.zeros_like(r_roads), where=R_roads>0)
    stay = stay_factor * rho * r_roads
    raw_out = r_roads - stay
    out = move_rate * raw_out
    hold = raw_out - out  # held back on i to smooth visuals

    # Preference scores S_{i,n}
    Dt = tau_current[None, :, :] - tau_current[:, None, :]   # Δτ[i,n,j] = τ[n]-τ[i]
    W = np.exp(-beta * Dt) * attr_vec[None, None, :]         # (N,N,S)
    S = W.sum(axis=2) * neighbors                            # (N,N)
    np.fill_diagonal(S, 0.0)

    # Remaining capacity before adding inflow this tick
    base = stay + hold
    rem_cap = np.maximum(R_roads - base, 0.0)
    inflow = np.zeros_like(r_roads)
    stranded = np.zeros_like(r_roads)

    # Process roads in random order to avoid bias
    order = rng.permutation(len(r_roads))
    for i in order:
        remaining = out[i]
        if remaining <= 1e-12:
            continue

        # pick best two destinations by S (that are neighbors)
        scores = S[i].copy()
        # mask out full destinations
        scores[rem_cap <= 1e-12] = 0.0
        if scores.max() <= 0.0:
            stranded[i] += remaining
            continue

        n1 = int(np.argmax(scores))
        scores[n1] = -np.inf
        n2 = int(np.argmax(scores)) if np.isfinite(scores).any() else None
        if n2 is not None and not np.isfinite(scores[n2]):
            n2 = None

        share1 = (1.0 - T_SECOND) * remaining
        share2 = T_SECOND * remaining

        # send to n1
        sent1 = min(share1, rem_cap[n1])
        inflow[n1] += sent1
        rem_cap[n1] -= sent1
        share1_left = share1 - sent1

        # send to n2 if it exists
        sent2 = 0.0
        if n2 is not None and rem_cap[n2] > 1e-12 and share2 > 0.0:
            sent2 = min(share2, rem_cap[n2])
            inflow[n2] += sent2
            rem_cap[n2] -= sent2
            share2_left = share2 - sent2
        else:
            share2_left = share2

        # OPTIONAL spillover (uncomment to spill leftovers to the other route instead of stranding)
        # if share1_left > 0 and n2 is not None and rem_cap[n2] > 1e-12:
        #     spill = min(share1_left, rem_cap[n2])
        #     inflow[n2] += spill
        #     rem_cap[n2] -= spill
        #     share1_left -= spill
        # if share2_left > 0 and rem_cap[n1] > 1e-12:
        #     spill = min(share2_left, rem_cap[n1])
        #     inflow[n1] += spill
        #     rem_cap[n1] -= spill
        #     share2_left -= spill

        stranded[i] += max(share1_left + share2_left, 0.0)

    r_pre = base + inflow + stranded
    r_pre = np.minimum(r_pre, R_roads + 1e-10)   # numerical safety
    r_roads_draw = r_pre.copy()
    r_roads = r_pre

def waterfill_send_from_road(i, target_indices, tau_weights, tgt_r, tgt_R, attr_vec, rate):
    global r_roads
    if len(target_indices) == 0: return 0.0
    caps_left = cap_left(tgt_r[target_indices], tgt_R[target_indices])
    if caps_left.sum() <= EPS: return 0.0
    w = attr_vec[target_indices] * np.exp(-beta * tau_weights)
    if w.sum() <= EPS: return 0.0
    remaining = rate * max(r_roads[i], 0.0)
    if remaining <= EPS: return 0.0
    sends = np.zeros_like(caps_left)
    mask = caps_left > EPS
    Wloc = w.copy()
    sent_total = 0.0
    # single-pass proportional (smoothed)
    denom = Wloc[mask].sum() if mask.any() else 0.0
    if denom > EPS:
        q = np.zeros_like(Wloc)
        q[mask] = Wloc[mask] / denom
        alloc = remaining * q
        take  = np.minimum(alloc, caps_left - sends)
        got   = float(take.sum())
        sends += take
        sent_total += got
    r_roads[i] -= sent_total
    tgt_r[target_indices] += sends
    return sent_total

def absorb_forward(rate):
    attr = attractiveness(r_sinks, R_sinks)
    total_sent = 0.0
    for i in range(N_roads):
        succ_sinks = [n for n in G.successors(f"R{i}") if n.startswith("S")]
        if not succ_sinks: continue
        J = np.array([int(s[1:]) for s in succ_sinks], dtype=int)
        tau_w = tau_S[i, J]
        total_sent += waterfill_send_from_road(i, J, tau_w, r_sinks, R_sinks, attr, rate=rate)
    return total_sent

def sinks_full_now():
    return bool(np.all(r_sinks >= R_sinks - 1e-9))

def sources_empty_now():
    return bool(np.all(r_sources <= 1e-9))

def total_mass():
    return float(r_sources.sum() + r_roads.sum() + r_sinks.sum())

# ---------- plotting ----------
fig, ax = plt.subplots(figsize=(8.5, 6.5))
cmap = plt.cm.plasma_r

def safe_ratio(num, den):
    num = np.asarray(num, float); den = np.asarray(den, float)
    return np.divide(num, den, out=np.zeros_like(num), where=den!=0)

def get_colors(r, R):
    rho = safe_ratio(r, R)
    rho = np.clip(rho, 0, 1)
    return cmap(rho)

def draw_labels(ax):
    for node, (x, y) in pos.items():
        if node.startswith("H"):
            idx = int(node[1:])
            pct = 100.0 * safe_ratio(r_sources[idx], R_sources[idx])
            w_val = w_sources[idx]
        elif node.startswith("R"):
            idx = int(node[1:])
            pct = 100.0 * safe_ratio(r_roads_draw[idx], R_roads[idx])  # pre-absorb display
            w_val = w_roads[idx]
        else:
            idx = int(node[1:])
            pct = 100.0 * safe_ratio(r_sinks[idx], R_sinks[idx])
            w_val = w_sinks[idx]
        ax.text(x, y - 0.35, f"{pct:.2f}%", ha="center", va="center", fontsize=9, color="black")
        ax.text(x, y - 0.55, f"w={w_val:.2f}", ha="center", va="center", fontsize=9, color="black")

# ---------- animate ----------
final_draining = False

def animate(_):
    global final_draining, r_roads_draw

    ax.clear()

    if not final_draining and not sources_empty_now():
        # Injection + capacity-constrained road redistribution + smoothed absorption
        inject_from_sources_forward()
        attr = attractiveness(r_sinks, R_sinks)
        constrained_road_redistribution(tau_S, attr, stay_factor=a, move_rate=MOVE_RATE_NORMAL)
        absorb_forward(rate=sink_rate)
    else:
        final_draining = True
        # Gentle multi-step drain per frame to avoid color jumps; still respects road caps
        for _ in range(FINAL_STEPS_PER_FRAME):
            attr = attractiveness(r_sinks, R_sinks)
            constrained_road_redistribution(tau_S, attr, stay_factor=FINAL_STAY, move_rate=MOVE_RATE_DRAIN)
            sent = absorb_forward(rate=FINAL_SINK_RATE)
            r_roads_draw = r_roads.copy()
            if sent < DRAIN_TOL and r_roads.sum() < DRAIN_TOL:
                break

    # draw
    node_colors = []
    for node in G.nodes():
        if node.startswith("H"):
            idx = int(node[1:])
            node_colors.append(get_colors(np.array([r_sources[idx]]), np.array([R_sources[idx]]))[0])
        elif node.startswith("R"):
            idx = int(node[1:])
            node_colors.append(get_colors(np.array([r_roads_draw[idx]]), np.array([R_roads[idx]]))[0])
        else:
            idx = int(node[1:])
            node_colors.append(get_colors(np.array([r_sinks[idx]]), np.array([R_sinks[idx]]))[0])

    nx.draw(G, pos, with_labels=True, ax=ax,
            node_color=node_colors, node_size=650,
            font_color="white", arrows=False)
    draw_labels(ax)

    # stop when done
    if sinks_full_now() and r_sources.sum() <= 1e-9 and r_roads.sum() <= 1e-9:
        r_sinks[:] = R_sinks
        ax.set_title(f"Finished — total mass = {total_mass():.2f}")
        fig.canvas.draw_idle()
        ani.event_source.stop()
    else:
        ax.set_title(f"Traffic distribution — total mass = {total_mass():.2f}")
    ax.set_axis_off()

ani = animation.FuncAnimation(fig, animate, frames=itertools.count(), interval=INTERVAL_MS, repeat=False)
plt.show()

import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

G = ox.graph_from_place("Dublin, Ireland", network_type="drive")


orig = ox.distance.nearest_nodes(G, -6.2546, 53.3438)   # Trinity College
dest = ox.distance.nearest_nodes(G, -6.2700, 53.4273)   # Airport

#min_distance
route = nx.shortest_path(G, orig, dest, weight="length")

fig, ax = ox.plot_graph(G, show=False, close=False)

#get nodes
node_positions = {node:(data['x'], data['y']) for node, data in G.nodes(data=True)}
route_coords = [node_positions[node] for node in route]

#roads
x, y = zip(*route_coords)
ax.plot(x, y, c="red", lw=3, alpha=0.7)

#Plot car 
(car,) = ax.plot([], [], "bo", markersize=10)

#Update animation
def update(frame):
    car.set_data([x[frame]], [y[frame]])  # wrap in []
    return car,

ani = FuncAnimation(fig, update, frames=len(route_coords), interval=500, blit=True, repeat=False)

plt.show()





#Giving Properties to nodes

nodes = list(G.nodes)
class Node:
    def __init__(self, node_id, occupationValue, relNodes, efficiency, location, node_var):
        self.node_id = node_id
        self.occupationValue = occupationValue
        self.relNodes = relNodes
        self.efficiency = efficiency
        self.location = location
        self.node_var = node_var

nodes = {}
for n, data in G.nodes(data=True):
    nodes[n] = Node(
        node_id=n,
        occupationValue=0,
        relNodes=list(G.neighbors(n)),
        efficiency=1.0,
        location=(data['x'], data['y']),
        node_var={}
    )

    


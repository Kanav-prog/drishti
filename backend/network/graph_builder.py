import networkx as nx
import json
import os

# --- DRISHTI LAYER 1: MASTER GRAPH BUILDER ---
# This engine mathematically proves structural vulnerability.
# Instead of observing local signal failures, we compute Betweenness Centrality
# across the entire interconnected Indian Railways network mock.

STATIONS = {
    # Northern Corridor
    "NDLS": {"name": "New Delhi", "zone": "NR", "lat": 28.6430, "lng": 77.2185},
    "AGC": {"name": "Agra Cantt", "zone": "NCR", "lat": 27.1581, "lng": 77.9904},
    "VGLJ": {"name": "Jhansi", "zone": "NCR", "lat": 25.4419, "lng": 78.5835},
    "BPL": {"name": "Bhopal", "zone": "WCR", "lat": 23.2647, "lng": 77.4116},
    "ET": {"name": "Itarsi Jn", "zone": "WCR", "lat": 22.6106, "lng": 77.7651}, # Massive bottleneck
    
    # Grand Chord / Eastern
    "CNB": {"name": "Kanpur", "zone": "NCR", "lat": 26.4357, "lng": 80.3235},
    "PRYJ": {"name": "Prayagraj", "zone": "NCR", "lat": 25.4414, "lng": 81.8291},
    "DDU": {"name": "Pt. Deen Dayal Upadhyay", "zone": "ECR", "lat": 25.2798, "lng": 83.1118}, # Massive bottleneck
    "PNBE": {"name": "Patna", "zone": "ECR", "lat": 25.6022, "lng": 85.1376},
    "DHN": {"name": "Dhanbad", "zone": "ECR", "lat": 23.7915, "lng": 86.4326},
    "ASN": {"name": "Asansol", "zone": "ER", "lat": 23.6841, "lng": 86.9744},
    "HWH": {"name": "Howrah", "zone": "ER", "lat": 22.5841, "lng": 88.3435},
    
    # North East
    "NJP": {"name": "New Jalpaiguri", "zone": "NFR", "lat": 26.6853, "lng": 88.4385},
    "GHY": {"name": "Guwahati", "zone": "NFR", "lat": 26.1820, "lng": 91.7515},

    # Western
    "MMCT": {"name": "Mumbai Central", "zone": "WR", "lat": 18.9696, "lng": 72.8194},
    "ST": {"name": "Surat", "zone": "WR", "lat": 21.2039, "lng": 72.8407},
    "BRC": {"name": "Vadodara", "zone": "WR", "lat": 22.3101, "lng": 73.1783},
    "RTM": {"name": "Ratlam", "zone": "WR", "lat": 23.3332, "lng": 75.0440},
    "KOTA": {"name": "Kota", "zone": "WCR", "lat": 25.1741, "lng": 75.8369},
    "MTJ": {"name": "Mathura", "zone": "NCR", "lat": 27.4870, "lng": 77.6749},

    # Central Cross / Southern
    "CSMT": {"name": "Mumbai CSMT", "zone": "CR", "lat": 18.9398, "lng": 72.8354},
    "KYN": {"name": "Kalyan", "zone": "CR", "lat": 19.2361, "lng": 73.1311},
    "BSL": {"name": "Bhusaval", "zone": "CR", "lat": 21.0531, "lng": 75.7925},
    "NGP": {"name": "Nagpur", "zone": "CR", "lat": 21.1472, "lng": 79.0881},
    "BPQ": {"name": "Balharshah", "zone": "CR", "lat": 19.8465, "lng": 79.3496},
    "KZJ": {"name": "Kazipet", "zone": "SCR", "lat": 17.9793, "lng": 79.5283},
    "SC": {"name": "Secunderabad", "zone": "SCR", "lat": 17.4337, "lng": 78.5016},
    "BZA": {"name": "Vijayawada", "zone": "SCR", "lat": 16.5193, "lng": 80.6305},
    "MAS": {"name": "Chennai Central", "zone": "SR", "lat": 13.0827, "lng": 80.2707},
    
    # Coromandel Coast
    "KGP": {"name": "Kharagpur", "zone": "SER", "lat": 22.3364, "lng": 87.3248},
    "BLS": {"name": "Balasore", "zone": "SER", "lat": 21.4984, "lng": 86.9205}, # The exact junction of focus
    "BBS": {"name": "Bhubaneswar", "zone": "ECoR", "lat": 20.2789, "lng": 85.8427},
    "VSKP": {"name": "Visakhapatnam", "zone": "ECoR", "lat": 17.7212, "lng": 83.2974},
    
    # Central/East links
    "R": {"name": "Raipur", "zone": "SECR", "lat": 21.2588, "lng": 81.6375},
    "BSP": {"name": "Bilaspur", "zone": "SECR", "lat": 22.0833, "lng": 82.1481},
    "TATA": {"name": "Tatanagar", "zone": "SER", "lat": 22.7667, "lng": 86.1963},
    
    # Deep South Interconnects
    "GTL": {"name": "Guntakal", "zone": "SCR", "lat": 15.1664, "lng": 77.3824},
    "WADI": {"name": "Wadi", "zone": "CR", "lat": 17.0620, "lng": 76.9926},
    "PUNE": {"name": "Pune", "zone": "CR", "lat": 18.5284, "lng": 73.8743},
    "SBC": {"name": "Bengaluru City", "zone": "SWR", "lat": 12.9784, "lng": 77.5684},
    "ED": {"name": "Erode", "zone": "SR", "lat": 11.3402, "lng": 77.7208},
    "ERS": {"name": "Ernakulam", "zone": "SR", "lat": 9.9658, "lng": 76.2929}
}

# Physical Links (Edges). Weights currently represent rough topological distance units.
EDGES = [
    ("NDLS", "MTJ", 1), ("MTJ", "AGC", 1), ("AGC", "VGLJ", 2), ("VGLJ", "BPL", 3),
    ("BPL", "ET", 1), ("ET", "NGP", 3), ("NGP", "BPQ", 2), ("BPQ", "KZJ", 2),
    ("KZJ", "SC", 1), ("KZJ", "BZA", 2), ("BZA", "MAS", 4),
    
    ("NDLS", "CNB", 4), ("CNB", "PRYJ", 2), ("PRYJ", "DDU", 1), 
    ("DDU", "PNBE", 2), ("DDU", "DHN", 3), ("PNBE", "ASN", 3), 
    ("DHN", "ASN", 1), ("ASN", "HWH", 2), ("ASN", "KGP", 2), # Major structural split
    
    ("PNBE", "NJP", 4), ("NJP", "GHY", 4),
    
    ("MMCT", "ST", 2), ("ST", "BRC", 1), ("BRC", "RTM", 2), ("RTM", "KOTA", 2),
    ("KOTA", "MTJ", 3),
    
    ("CSMT", "KYN", 1), ("KYN", "BSL", 3), ("BSL", "AK", 1), ("BSL", "ET", 3), # Interconnect ET and BSL
    ("AK", "NGP", 2), ("NGP", "R", 3), ("R", "BSP", 1), ("BSP", "TATA", 3), 
    ("TATA", "KGP", 1), ("KGP", "HWH", 1),
    
    ("HWH", "KGP", 1), ("KGP", "BLS", 1), ("BLS", "BBS", 2), # Balasore precisely on the heavily-loaded node chain
    ("BBS", "VSKP", 4), ("VSKP", "BZA", 3),
    
    ("CSMT", "PUNE", 1), ("PUNE", "WADI", 3), ("WADI", "GTL", 2), ("GTL", "MAS", 3),
    ("WADI", "SC", 2), ("MAS", "ED", 3), ("ED", "ERS", 2), ("ED", "SBC", 2),
    ("GTL", "SBC", 2)
]

def build_and_evaluate_graph():
    G = nx.Graph()
    
    print("Layer 1: Initializing DRISHTI NetworkX Core...")
    for node_id, data in STATIONS.items():
        G.add_node(node_id, **data)
        
    for u, v, w in EDGES:
        try:
            G.add_edge(u, v, weight=w)
        except Exception as e:
            print(f"Warning mapping edge {u}-{v}: {e}")
        
    print(f"Network mapped: {G.number_of_nodes()} Junctions, {G.number_of_edges()} Corridors.")
    
    # Calculate Betweenness Centrality (Unweighted, as physical infrastructure chokepoints matter most)
    centrality = nx.betweenness_centrality(G, normalized=True)
    
    # Sort and enrich
    ranked_nodes = []
    for node_id, score in centrality.items():
        # Inject the computed score into the node payload
        G.nodes[node_id]["centrality"] = score
        ranked_nodes.append({
            "id": node_id,
            "name": STATIONS[node_id]["name"],
            "zone": STATIONS[node_id]["zone"],
            "centrality_score": round(score, 4),
            "lat": STATIONS[node_id]["lat"],
            "lng": STATIONS[node_id]["lng"]
        })
        
    ranked_nodes.sort(key=lambda x: x["centrality_score"], reverse=True)
    
    print("\\nDRISHTI INTELLIGENCE: TOP 10 CASCADE-VULNERABLE NODES:")
    for i, n in enumerate(ranked_nodes[:10], 1):
        print(f" {i}. {n['id']} ({n['name']}) - Centrality: {n['centrality_score']}")
        
    # Serialize the graph into a format the React/D3 frontend can directly render
    nodes_export = [{"id": n, **G.nodes[n]} for n in G.nodes()]
    edges_export = [{"source": u, "target": v, "weight": G[u][v]["weight"]} for u, v in G.edges()]
    
    output_payload = {
        "nodes": ranked_nodes,  # For easy list iteration
        "graph": {
            "nodes": nodes_export,
            "links": edges_export
        }
    }
    
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "network_graph.json")
    
    with open(out_file, "w") as f:
        json.dump(output_payload, f, indent=2)
        
    print(f"\\n[OK] Network Model generated and saved to {out_file}")
    
if __name__ == "__main__":
    if "AK" not in STATIONS:
        STATIONS["AK"] = {"name": "Akola", "zone": "CR", "lat": 20.7028, "lng": 77.0097}
    build_and_evaluate_graph()

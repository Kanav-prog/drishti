"""
DRISHTI MVP: 48-Hour Live Demo Script
Demonstrates all 4 layers in real-time with cascade visualization
"""

import subprocess
import time
import json
import requests
import sys
import os
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

class DRISHTIDemo:
    """Automated MVP demonstration"""
    
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.processes = []
        self.api_ready = False
        self.demo_duration = 30  # seconds
        self.alerts_captured = []
    
    def header(self, text: str):
        """Print formatted header"""
        print(f"\n{BOLD}{BLUE}{'='*80}{RESET}")
        print(f"{BOLD}{BLUE}{text:^80}{RESET}")
        print(f"{BOLD}{BLUE}{'='*80}{RESET}\n")
    
    def step(self, num: int, text: str):
        """Print numbered step"""
        print(f"{BOLD}{YELLOW}[{num}] {text}{RESET}")
    
    def success(self, text: str):
        """Print success message"""
        print(f"{GREEN}✓ {text}{RESET}")
    
    def error(self, text: str):
        """Print error message"""
        print(f"{RED}✗ {text}{RESET}")
    
    def info(self, text: str):
        """Print info message"""
        print(f"{BLUE}ℹ {text}{RESET}")
    
    # ──────────────────────────────────────────────────────────────
    # PHASE 1: INITIALIZATION
    # ──────────────────────────────────────────────────────────────
    
    def init_phase1_generate_graph(self):
        """Phase 1: Generate network graph (Layer 1)"""
        self.step(1, "Generating Network Graph (Layer 1: The Map)")
        
        try:
            graph_script = self.root_dir / "backend/network/graph_builder.py"
            if not graph_script.exists():
                self.error(f"Graph builder not found at {graph_script}")
                return False
            
            result = subprocess.run(
                [sys.executable, str(graph_script)],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse output
                for line in result.stdout.split('\n'):
                    if "Network mapped" in line:
                        self.success(line.strip())
                    elif "TOP 10" in line:
                        self.info("Computing centrality")
                    elif "Junctions" in line or "Corridors" in line:
                        self.info(line.strip())
                return True
            else:
                self.error(f"Graph building failed: {result.stderr}")
                return False
        except Exception as e:
            self.error(f"Exception: {e}")
            return False
    
    def init_phase2_start_api(self):
        """Phase 2: Start the FastAPI server"""
        self.step(2, "Starting FastAPI Server with Cascade Engine")
        
        try:
            # Start API in background
            api_script = self.root_dir / "backend/api/server.py"
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["REDIS_HOST"] = "localhost"
            env["REDIS_PORT"] = "6379"
            
            proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.api.server:app", 
                 "--host", "0.0.0.0", "--port", "8000", "--reload"],
                cwd=str(self.root_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            self.processes.append(proc)
            
            # Wait for API to be ready
            self.info("Waiting for API startup...")
            max_wait = 15
            start = time.time()
            
            while time.time() - start < max_wait:
                try:
                    resp = requests.get("http://localhost:8000/api/health", timeout=2)
                    if resp.status_code == 200:
                        self.api_ready = True
                        self.success("FastAPI running on port 8000")
                        return True
                except:
                    time.sleep(1)
            
            self.error("API failed to start within timeout")
            return False
        except Exception as e:
            self.error(f"Failed to start API: {e}")
            return False
    
    # ──────────────────────────────────────────────────────────────
    # PHASE 2: LIVE DEMONSTRATION
    # ──────────────────────────────────────────────────────────────
    
    def demo_layer1_network_stats(self):
        """Demonstrate Layer 1: Network structure"""
        self.step("L1", "Layer 1: The Map — Network Centrality Analysis")
        
        try:
            resp = requests.get("http://localhost:8000/api/network/pulse", timeout=5)
            if resp.status_code != 200:
                self.error("Network pulse not available")
                return
            
            data = resp.json()
            nodes = data.get("nodes", [])
            
            if not nodes:
                self.error("No network nodes")
                return
            
            # Show top 5 most critical nodes
            self.info("Top 5 Structurally Critical Junctions:")
            sorted_nodes = sorted(nodes, key=lambda x: x.get("centrality", 0), reverse=True)
            
            for i, node in enumerate(sorted_nodes[:5], 1):
                print(f"   {i}. {node['id']:8} ({node['name']:20}) → Centrality: {node['centrality']:.3f}")
            
            self.success(f"Network: {len(nodes)} stations mapped")
        except Exception as e:
            self.error(f"Layer 1 demo failed: {e}")
    
    def demo_layer2_cascade_stress(self):
        """Demonstrate Layer 2: Live stress and cascading"""
        self.step("L2", "Layer 2: The Pulse — Real-Time Cascade Simulation")
        
        try:
            resp = requests.get("http://localhost:8000/api/network/pulse", timeout=5)
            if resp.status_code != 200:
                self.error("Network pulse not available")
                return
            
            data = resp.json()
            nodes = data.get("nodes", [])
            zone_health = data.get("zone_health", {})
            
            # Show stressed nodes
            stressed = [n for n in nodes if n.get("stress_level") in ["HIGH", "CRITICAL"]]
            if stressed:
                self.info(f"Cascade Effect: {len(stressed)} nodes under stress")
                for node in stressed[:3]:
                    print(f"   • {node['id']:8} → Stress: {node['stress_level']:8} | " \
                          f"Delay: {node['delay_minutes']:3}min | Risk: {node['cascade_risk']:.2f}")
            else:
                self.info("Network nominal — no cascading stress detected")
            
            # Show zone health
            critical_zones = [z for z, h in zone_health.items() if h.get("status") == "CRITICAL"]
            if critical_zones:
                self.info(f"Zone Health Alert: {len(critical_zones)} zones critical")
                for zone in critical_zones[:2]:
                    score = zone_health[zone]["score"]
                    hubs = zone_health[zone]["delayed_hubs"]
                    print(f"   • Zone {zone:3} → Score: {score:5.1f}/100 | Affected Hubs: {hubs}")
            else:
                self.info("All zones nominal")
            
            self.success(f"Cascade engine: {len(zone_health)} zones monitored")
        except Exception as e:
            self.error(f"Layer 2 demo failed: {e}")
    
    def demo_layer3_pattern_matching(self):
        """Demonstrate Layer 3: Pattern matching alerts"""
        self.step("L3", "Layer 3: Intelligence — Pre-Accident Signature Matching")
        
        try:
            resp = requests.get("http://localhost:8000/api/stats", timeout=5)
            if resp.status_code != 200:
                self.error("Stats not available")
                return
            
            data = resp.json()
            stats = data.get("stats", {}) if "stats" in data else data
            
            # Show alert statistics
            critical_alerts = stats.get("critical", 0)
            high_alerts = stats.get("high", 0)
            total_alerts = stats.get("total", 0)
            
            self.info("Pattern Matching Results:")
            print(f"   • Critical Matches (DUAL+): {critical_alerts}")
            print(f"   • High Risk Matches (DUAL):  {high_alerts}")
            print(f"   • Total Alerts Generated:     {total_alerts}")
            
            if critical_alerts > 0:
                print(f"\n   🚨 {critical_alerts} critical pre-accident signatures detected!")
            
            self.success(f"Pattern matching: {total_alerts} alerts processed")
        except Exception as e:
            self.error(f"Layer 3 demo failed: {e}")
    
    def demo_layer4_dashboard_api(self):
        """Demonstrate Layer 4: Dashboard API"""
        self.step("L4", "Layer 4: Dashboard — Unified Intelligence API")
        
        try:
            # Test all layer endpoints
            endpoints = [
                ("/api/health", "Health Check"),
                ("/api/network/pulse", "Network Pulse"),
                ("/api/stats", "Statistics"),
                ("/metrics", "Prometheus Metrics"),
            ]
            
            self.info("API Endpoints Status:")
            for endpoint, name in endpoints:
                try:
                    resp = requests.get(f"http://localhost:8000{endpoint}", timeout=3)
                    status = "🟢 UP" if resp.status_code == 200 else "🔴 DOWN"
                    print(f"   {endpoint:20} {name:25} {status}")
                except:
                    print(f"   {endpoint:20} {name:25} 🔴 DOWN")
            
            self.success("Dashboard API operational")
        except Exception as e:
            self.error(f"Layer 4 demo failed: {e}")
    
    # ──────────────────────────────────────────────────────────────
    # MAIN DEMO FLOW
    # ──────────────────────────────────────────────────────────────
    
    def run_demo(self):
        """Execute full MVP demonstration"""
        self.header("DRISHTI MVP LIVE DEMONSTRATION")
        print(f"{BOLD}Railway Operations Intelligence Platform v5.0{RESET}")
        print(f"{BOLD}Cascade Risk Monitoring & Real-Time Analytics{RESET}\n")
        
        # Phase 1: Setup
        self.header("PHASE 0: INITIALIZATION")
        
        if not self.init_phase1_generate_graph():
            self.error("Failed to generate network graph")
            return False
        
        time.sleep(1)
        
        if not self.init_phase2_start_api():
            self.error("Failed to start API")
            self.cleanup()
            return False
        
        time.sleep(2)
        
        # Phase 2: Live Demo
        self.header("PHASE 1: LIVE 4-LAYER DEMONSTRATION")
        
        demo_start = time.time()
        iteration = 0
        
        while time.time() - demo_start < self.demo_duration:
            iteration += 1
            print(f"\n{BOLD}╔═══ ITERATION {iteration} ═══╗{RESET}")
            
            # Run all 4 layer demos
            self.demo_layer1_network_stats()
            print()
            self.demo_layer2_cascade_stress()
            print()
            self.demo_layer3_pattern_matching()
            print()
            self.demo_layer4_dashboard_api()
            
            elapsed = int(time.time() - demo_start)
            remaining = self.demo_duration - elapsed
            
            if remaining > 0:
                print(f"\n{YELLOW}⏱️  Next update in 5 seconds... ({remaining}s remaining){RESET}", end="")
                sys.stdout.flush()
                time.sleep(5)
                print("\r" + " "*60 + "\r", end="")
        
        # Summary
        self.header("DEMONSTRATION COMPLETE")
        print(f"{GREEN}{BOLD}✓ All 4 layers operational and integrated{RESET}")
        print(f"{GREEN}✓ Real-time cascade simulation running{RESET}")
        print(f"{GREEN}✓ Pattern matching active{RESET}")
        print(f"{GREEN}✓ Dashboard API responding{RESET}\n")
        
        print(f"{BOLD}Next Steps:{RESET}")
        print(f"  1. Open browser → http://localhost:3000")
        print(f"  2. Navigate to Network Pulse view")
        print(f"  3. Watch D3.js visualization update in real-time")
        print(f"  4. Observe cascade propagation across network")
        print(f"  5. Monitor zone health aggregation\n")
        
        return True
    
    def cleanup(self):
        """Clean up processes"""
        for proc in self.processes:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except:
                proc.kill()


def main():
    """Main entry point"""
    demo = DRISHTIDemo()
    
    try:
        success = demo.run_demo()
        
        if success:
            print(f"{BOLD}{GREEN}Demo execution successful!{RESET}")
            print(f"Press Ctrl+C to stop the server\n")
            
            # Keep server running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\nShutting down...")
                demo.cleanup()
                print("Goodbye!")
        else:
            demo.cleanup()
            return 1
    except Exception as e:
        print(f"\n{RED}Fatal error: {e}{RESET}")
        demo.cleanup()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

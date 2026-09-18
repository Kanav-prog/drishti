<!-- 
CASCADE & NETWORK VISUALIZATION
Real-time D3 network showing IR topology + cascade propagation + live trains
-->

<template>
  <div class="network-viz">
    <div class="viz-header">
      <h2>🗺️ Real-time Network Visualization</h2>
      <div class="viz-controls">
        <button @click="toggleCascadeMode" :class="{ active: showCascade }">
          Show Cascade
        </button>
        <button @click="toggleTrainMode" :class="{ active: showTrains }">
          Show Trains
        </button>
        <button @click="zoomReset">Reset Zoom</button>
      </div>
    </div>

    <svg ref="networkSvg" class="network-svg"></svg>

    <!-- LEGEND -->
    <div class="legend">
      <div class="legend-item">
        <div class="legend-color hub"></div>
        <span>Critical Junction</span>
      </div>
      <div class="legend-item">
        <div class="legend-color junction"></div>
        <span>Regular Junction</span>
      </div>
      <div class="legend-item">
        <div class="legend-color train-dot"></div>
        <span>Train Position</span>
      </div>
      <div class="legend-item">
        <div class="legend-line cascade"></div>
        <span>Cascade Edge</span>
      </div>
    </div>

    <!-- TOOLTIP -->
    <div v-if="tooltip.visible" class="tooltip" :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
      <strong>{{ tooltip.title }}</strong>
      <p>{{ tooltip.content }}</p>
    </div>
  </div>
</template>

<script>
import * as d3 from 'd3';

export default {
  name: 'NetworkVisualization',
  data() {
    return {
      svg: null,
      simulation: null,
      showCascade: true,
      showTrains: true,
      tooltip: {
        visible: false,
        x: 0,
        y: 0,
        title: '',
        content: '',
      },
      nodes: [
        { id: 'NDLS', label: 'New Delhi', centrality: 1.0, type: 'hub' },
        { id: 'HWH', label: 'Howrah', centrality: 0.94, type: 'hub' },
        { id: 'BOMBAY', label: 'Mumbai', centrality: 0.92, type: 'hub' },
        { id: 'MAS', label: 'Chennai', centrality: 0.88, type: 'hub' },
        { id: 'SC', label: 'Hyderabad', centrality: 0.81, type: 'hub' },
        { id: 'NGP', label: 'Nagpur', centrality: 0.75, type: 'junction' },
        { id: 'ALD', label: 'Prayagraj', centrality: 0.78, type: 'junction' },
        { id: 'BZA', label: 'Vijayawada', centrality: 0.80, type: 'junction' },
        { id: 'LKO', label: 'Lucknow', centrality: 0.71, type: 'junction' },
        { id: 'CNB', label: 'Kanpur', centrality: 0.69, type: 'junction' },
      ],
      links: [
        { source: 'NDLS', target: 'ALD' },
        { source: 'NDLS', target: 'LKO' },
        { source: 'NDLS', target: 'CNB' },
        { source: 'ALD', target: 'MGS' },
        { source: 'MGS', target: 'PNBE' },
        { source: 'PNBE', target: 'HWH' },
        { source: 'HWH', target: 'KGP' },
        { source: 'BOMBAY', target: 'ET' },
        { source: 'ET', target: 'NGP' },
        { source: 'NGP', target: 'SC' },
        { source: 'SC', target: 'BZA' },
        { source: 'BZA', target: 'MAS' },
        { source: 'NDLS', target: 'BOMBAY' },
        { source: 'BOMBAY', target: 'MAS' },
        { source: 'HWH', target: 'MAS' },
      ],
      cascadeEdges: [
        { source: 'NDLS', target: 'CNB' },
        { source: 'CNB', target: 'LKO' },
        { source: 'LKO', target: 'ALD' },
      ],
      trains: [
        { id: '12001', junction: 'NDLS', delay: 120, status: 'emergency' },
        { id: '12002', junction: 'CNB', delay: 95, status: 'critical' },
        { id: '12301', junction: 'ALD', delay: 50, status: 'warning' },
        { id: '14031', junction: 'BOMBAY', delay: 10, status: 'normal' },
      ],
    };
  },
  mounted() {
    this.initializeVisualization();
  },
  methods: {
    initializeVisualization() {
      const container = this.$refs.networkSvg.parentElement;
      const width = container.clientWidth;
      const height = 600;

      this.svg = d3
        .select(this.$refs.networkSvg)
        .attr('width', width)
        .attr('height', height);

      // Create zoom behavior
      const zoom = d3.zoom().on('zoom', (event) => {
        this.svg.select('g').attr('transform', event.transform);
      });
      this.svg.call(zoom);

      // Create container group
      const g = this.svg.append('g');

      // Create simulation
      this.simulation = d3
        .forceSimulation(this.nodes)
        .force('link', d3.forceLink(this.links).id((d) => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-500))
        .force('center', d3.forceCenter(width / 2, height / 2));

      // Draw edges
      const link = g
        .selectAll('.link')
        .data(this.links)
        .enter()
        .append('line')
        .attr('class', 'link')
        .attr('stroke', '#666')
        .attr('stroke-width', 2);

      // Draw cascade edges (overlay)
      const cascadeLink = g
        .selectAll('.cascade-link')
        .data(this.cascadeEdges)
        .enter()
        .append('line')
        .attr('class', 'cascade-link')
        .attr('stroke', '#ff4444')
        .attr('stroke-width', 3)
        .attr('opacity', this.showCascade ? 0.8 : 0)
        .attr('stroke-dasharray', '5,5');

      // Draw nodes
      const node = g
        .selectAll('.node')
        .data(this.nodes)
        .enter()
        .append('circle')
        .attr('class', 'node')
        .attr('r', (d) => 15 + d.centrality * 20)
        .attr('fill', (d) => (d.type === 'hub' ? '#ff4444' : '#1e90ff'))
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .on('mouseover', (event, d) => this.showTooltip(event, d))
        .on('mouseout', () => this.hideTooltip());

      // Draw train dots
      const trainDots = g
        .selectAll('.train')
        .data(this.trains)
        .enter()
        .append('circle')
        .attr('class', 'train')
        .attr('r', 8)
        .attr('fill', (d) => {
          switch (d.status) {
            case 'emergency':
              return '#ff0000';
            case 'critical':
              return '#ff4444';
            case 'warning':
              return '#ffaa00';
            default:
              return '#00ff00';
          }
        })
        .attr('opacity', this.showTrains ? 0.8 : 0);

      // Add labels
      const label = g
        .selectAll('.label')
        .data(this.nodes)
        .enter()
        .append('text')
        .attr('class', 'label')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .text((d) => d.id)
        .attr('fill', '#fff')
        .attr('font-size', '10px');

      // Update positions on simulation tick
      this.simulation.on('tick', () => {
        link
          .attr('x1', (d) => d.source.x)
          .attr('y1', (d) => d.source.y)
          .attr('x2', (d) => d.target.x)
          .attr('y2', (d) => d.target.y);

        cascadeLink
          .attr('x1', (d) => d.source.x)
          .attr('y1', (d) => d.source.y)
          .attr('x2', (d) => d.target.x)
          .attr('y2', (d) => d.target.y);

        node.attr('cx', (d) => d.x).attr('cy', (d) => d.y);

        trainDots.attr('cx', (d) => {
          const node = this.nodes.find((n) => n.id === d.junction);
          return node ? node.x : 0;
        })
        .attr('cy', (d) => {
          const node = this.nodes.find((n) => n.id === d.junction);
          return node ? node.y : 0;
        });

        label.attr('x', (d) => d.x).attr('y', (d) => d.y);
      });
    },
    toggleCascadeMode() {
      this.showCascade = !this.showCascade;
      this.svg
        .selectAll('.cascade-link')
        .attr('opacity', this.showCascade ? 0.8 : 0);
    },
    toggleTrainMode() {
      this.showTrains = !this.showTrains;
      this.svg
        .selectAll('.train')
        .attr('opacity', this.showTrains ? 0.8 : 0);
    },
    zoomReset() {
      this.svg.transition().duration(750).call(
        d3.zoom().transform,
        d3.zoomIdentity.translate(0, 0).scale(1)
      );
    },
    showTooltip(event, d) {
      this.tooltip.visible = true;
      this.tooltip.x = event.pageX;
      this.tooltip.y = event.pageY;
      this.tooltip.title = d.label;
      this.tooltip.content = `Centrality: ${(d.centrality * 100).toFixed(0)}%`;
    },
    hideTooltip() {
      this.tooltip.visible = false;
    },
  },
};
</script>

<style scoped>
.network-viz {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
}

.viz-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  border-bottom: 1px solid #333;
  padding-bottom: 15px;
}

.viz-header h2 {
  margin: 0;
  color: #1e90ff;
  font-size: 1.3em;
}

.viz-controls {
  display: flex;
  gap: 10px;
}

.viz-controls button {
  padding: 8px 16px;
  background: #252525;
  border: 1px solid #1e90ff;
  color: #1e90ff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85em;
  transition: all 0.3s;
}

.viz-controls button:hover {
  background: #1e90ff;
  color: #1a1a1a;
}

.viz-controls button.active {
  background: #1e90ff;
  color: #1a1a1a;
}

.network-svg {
  width: 100%;
  height: 600px;
  background: #0f0f0f;
  border-radius: 4px;
}

.link {
  fill: none;
}

.cascade-link {
  stroke-linecap: round;
}

.node {
  cursor: pointer;
  transition: r 0.3s;
}

.node:hover {
  filter: brightness(1.3);
}

.train {
  filter: drop-shadow(0 0 3px currentColor);
}

.label {
  font-weight: bold;
  pointer-events: none;
}

.legend {
  display: flex;
  gap: 20px;
  margin-top: 15px;
  padding: 12px;
  background: #0f0f0f;
  border-radius: 4px;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85em;
  color: #aaa;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid #666;
}

.legend-color.hub {
  background: #ff4444;
}

.legend-color.junction {
  background: #1e90ff;
}

.legend-color.train-dot {
  background: #ffaa00;
}

.legend-line {
  width: 16px;
  height: 2px;
  background: #ff4444;
}

.legend-line.cascade {
  background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="2"><line x1="0" y1="1" x2="16" y2="1" stroke="rgb(255,68,68)" stroke-width="2" stroke-dasharray="5,5"/></svg>');
  background-repeat: repeat-x;
}

.tooltip {
  position: fixed;
  background: #252525;
  border: 1px solid #1e90ff;
  border-radius: 4px;
  padding: 8px 12px;
  font-size: 0.85em;
  color: #e0e0e0;
  z-index: 1000;
  pointer-events: none;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}

.tooltip strong {
  color: #1e90ff;
}

.tooltip p {
  margin: 4px 0 0 0;
  color: #aaa;
}
</style>


import React, { useEffect, useRef, useMemo, useState } from 'react';
import * as d3 from 'd3';
import { PolicyNode, PolicyLink } from '../types';
import { RefreshCw, Eye, EyeOff } from 'lucide-react';

interface NetworkGraphProps {
  nodes: PolicyNode[];
  links: PolicyLink[];
  width?: number;
  height?: number;
  onNodeClick?: (node: PolicyNode) => void;
}

const NetworkGraph: React.FC<NetworkGraphProps> = ({ nodes, links, width = 800, height = 600, onNodeClick }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const gRef = useRef<SVGGElement>(null);
  
  // Legend Toggle State
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());

  // Define color mapping based on node type
  const typeColor = (type: string) => {
    switch (type) {
      case 'actor': return '#60a5fa'; // Blue-400
      case 'policy': return '#a78bfa'; // Purple-400
      case 'outcome': return '#34d399'; // Emerald-400
      case 'risk': return '#ef4444'; // Red-500
      default: return '#94a3b8';
    }
  };

  const glowColor = (type: string) => {
      switch (type) {
      case 'actor': return 'rgba(96, 165, 250, 0.6)';
      case 'policy': return 'rgba(167, 139, 250, 0.6)';
      case 'outcome': return 'rgba(52, 211, 153, 0.6)';
      case 'risk': return 'rgba(239, 68, 68, 0.6)';
      default: return 'rgba(148, 163, 184, 0.3)';
    }
  }

  // Filter Data based on Legend Toggles
  const filteredData = useMemo(() => {
    const activeNodes = nodes.filter(n => !hiddenTypes.has(n.type)).map(d => ({...d}));
    const activeNodeIds = new Set(activeNodes.map(n => n.id));
    
    const activeLinks = links
        .filter(l => activeNodeIds.has(l.source) && activeNodeIds.has(l.target))
        .map(d => ({...d}));
        
    return { nodes: activeNodes, links: activeLinks };
  }, [nodes, links, hiddenTypes]);

  // Handle Zoom Reset
  const handleResetZoom = () => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom().on("zoom", (event) => {
       if (gRef.current) {
          d3.select(gRef.current).attr("transform", event.transform);
       }
    });
    // @ts-ignore
    svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
  };

  const toggleType = (type: string) => {
      const newHidden = new Set(hiddenTypes);
      if (newHidden.has(type)) {
          newHidden.delete(type);
      } else {
          newHidden.add(type);
      }
      setHiddenTypes(newHidden);
  };

  useEffect(() => {
    if (!svgRef.current || !gRef.current) return;

    const svg = d3.select(svgRef.current);
    const g = d3.select(gRef.current);
    
    // Clear previous render contents
    g.selectAll("*").remove();

    // Setup Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom)
       .on("dblclick.zoom", null); // Disable double click zoom

    // If no nodes, just return after clearing
    if (filteredData.nodes.length === 0) return;

    const simulation = d3.forceSimulation(filteredData.nodes as d3.SimulationNodeDatum[])
      .force("link", d3.forceLink(filteredData.links).id((d: any) => d.id).distance(120))
      .force("charge", d3.forceManyBody().strength(-400))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide().radius(40).strength(0.7));

    // Links
    const link = g.append("g")
      .attr("stroke-opacity", 0.6)
      .selectAll("line")
      .data(filteredData.links)
      .join("line")
      .attr("stroke", "#475569")
      .attr("stroke-width", (d) => Math.sqrt(d.strength) * 0.8);

    // Node Groups
    const node = g.append("g")
      .selectAll("g")
      .data(filteredData.nodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(drag(simulation) as any)
      .on("click", (event, d: any) => {
          event.stopPropagation();
          const originalNode = nodes.find(n => n.id === d.id);
          if (originalNode && onNodeClick) {
              onNodeClick(originalNode);
          }
      })
      .on("mouseover", function(event, d) {
          d3.select(this).selectAll("circle").transition().duration(200).attr("transform", "scale(1.2)");
      })
      .on("mouseout", function(event, d) {
          d3.select(this).selectAll("circle").transition().duration(200).attr("transform", "scale(1)");
      });

    // Glow effect circle (background)
    node.append("circle")
        .attr("r", (d) => 8 + (d.impactScore / 8))
        .attr("fill", (d) => glowColor(d.type))
        .attr("filter", "blur(8px)")
        .attr("opacity", 0.6);

    // Main Node Circle
    node.append("circle")
      .attr("r", (d) => 5 + (d.impactScore / 12))
      .attr("fill", (d) => typeColor(d.type))
      .attr("stroke", "#0f172a")
      .attr("stroke-width", 2);

    // Labels
    node.append("text")
      .text((d) => d.label)
      .attr("x", 14)
      .attr("y", 5)
      .attr("fill", "#e2e8f0")
      .attr("font-family", "JetBrains Mono")
      .attr("font-size", "11px")
      .attr("font-weight", "500")
      .style("pointer-events", "none")
      .style("text-shadow", "0 0 4px #000, 0 0 2px #000");

    // Simulation Tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node
        .attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    function drag(simulation: d3.Simulation<d3.SimulationNodeDatum, undefined>) {
      function dragstarted(event: any) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      }

      function dragged(event: any) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }

      function dragended(event: any) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      }

      return d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended);
    }

    // Cleanup
    return () => {
      simulation.stop();
      svg.on(".zoom", null);
    };
  }, [filteredData, width, height, onNodeClick]);

  return (
    <div className="w-full h-full relative overflow-hidden rounded-xl border border-nexus-800 bg-nexus-900/30">
        
        {/* Interactive Graph Legend */}
        <div className="absolute top-4 left-4 z-10 flex flex-col gap-2 select-none bg-nexus-950/60 p-3 rounded-lg backdrop-blur-sm border border-nexus-800/30 shadow-xl">
            {[
                { type: 'actor', label: 'ACTOR', color: 'bg-blue-400', shadow: 'rgba(96,165,250,0.5)' },
                { type: 'policy', label: 'POLICY', color: 'bg-purple-400', shadow: 'rgba(167,139,250,0.5)' },
                { type: 'outcome', label: 'OUTCOME', color: 'bg-emerald-400', shadow: 'rgba(52,211,153,0.5)' },
                { type: 'risk', label: 'RISK', color: 'bg-red-500', shadow: 'rgba(239,68,68,0.5)' },
            ].map((item) => (
                <button 
                    key={item.type}
                    onClick={() => toggleType(item.type)}
                    className={`flex items-center gap-3 p-1.5 rounded transition-all duration-200 group ${hiddenTypes.has(item.type) ? 'opacity-40 hover:opacity-60' : 'opacity-100'}`}
                >
                    <div className={`w-2.5 h-2.5 rounded-full ${item.color}`} style={{ boxShadow: hiddenTypes.has(item.type) ? 'none' : `0 0 8px ${item.shadow}` }}></div>
                    <span className={`text-[10px] font-mono tracking-wider ${hiddenTypes.has(item.type) ? 'text-slate-500 line-through' : 'text-slate-300'}`}>{item.label}</span>
                    <div className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                         {hiddenTypes.has(item.type) ? <EyeOff className="w-3 h-3 text-slate-500"/> : <Eye className="w-3 h-3 text-slate-400"/>}
                    </div>
                </button>
            ))}
        </div>

        {/* Zoom Controls */}
        <div className="absolute bottom-4 right-4 z-10 flex gap-2">
            <button 
                onClick={handleResetZoom}
                className="p-2 bg-nexus-800/80 hover:bg-nexus-700 text-slate-300 rounded-lg border border-nexus-700 backdrop-blur transition-all active:scale-95 shadow-lg"
                title="Reset View"
            >
                <RefreshCw className="w-4 h-4" />
            </button>
        </div>
        
      <svg ref={svgRef} width={width} height={height} className="w-full h-full cursor-move">
        <g ref={gRef}></g>
      </svg>
    </div>
  );
};

export default NetworkGraph;

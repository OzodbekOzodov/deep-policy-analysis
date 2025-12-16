import React, { useRef, useEffect, useState } from 'react';
import {
    Activity,
    Cpu,
    Globe,
    Search,
    Database,
    Share2,
    ShieldAlert,
    Terminal,
    Zap,
    ArrowLeft,
    RefreshCw
} from 'lucide-react';
import NetworkGraph from './NetworkGraph';
import SimulationCharts from './SimulationCharts';
import DataTerminal from './DataTerminal';
import EntityDetailPanel from './EntityDetailPanel';
import { SimulationData, AgentLog, AnalysisState, PolicyNode } from '../types';

interface DashboardViewProps {
    query: string;
    setQuery: (q: string) => void;
    simulationData: SimulationData;
    state: AnalysisState;
    logs: AgentLog[];
    onBack: () => void;
    onRefresh: () => void;
}

const DashboardView: React.FC<DashboardViewProps> = ({
    query,
    setQuery,
    simulationData,
    state,
    logs,
    onBack,
    onRefresh
}) => {
    const [selectedNode, setSelectedNode] = useState<PolicyNode | null>(null);
    const [containerDimensions, setContainerDimensions] = useState({ width: 800, height: 600 });
    const graphContainerRef = useRef<HTMLDivElement>(null);
    const isMounted = useRef(true);

    useEffect(() => {
        isMounted.current = true;
        return () => { isMounted.current = false; };
    }, []);

    // Resize observer for graph
    useEffect(() => {
        if (!graphContainerRef.current) return;
        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                if (isMounted.current) {
                    setContainerDimensions({
                        width: entry.contentRect.width,
                        height: entry.contentRect.height
                    });
                }
            }
        });
        observer.observe(graphContainerRef.current);
        return () => observer.disconnect();
    }, [isMounted]);

    const handleNodeClick = (node: PolicyNode) => {
        setSelectedNode(node);
    };

    const closeDetailPanel = () => {
        setSelectedNode(null);
    };

    return (
        <div className="flex h-screen w-screen bg-nexus-950 text-slate-200 overflow-hidden font-sans selection:bg-nexus-500 selection:text-white">

            {/* LEFT SIDEBAR - CONTROL & METRICS */}
            <div className="w-80 flex flex-col border-r border-nexus-800 bg-nexus-950/80 backdrop-blur-xl z-20 shadow-2xl">
                <div className="p-4 border-b border-nexus-800">
                    <div className="flex items-center gap-2 mb-2">
                        <button onClick={onBack} className="p-1 hover:bg-nexus-900 rounded text-slate-500 hover:text-slate-300 transition-colors">
                            <ArrowLeft className="w-4 h-4" />
                        </button>
                        <h1 className="text-xl font-mono font-bold tracking-tighter text-white flex items-center gap-2">
                            <Cpu className="text-nexus-accent animate-pulse-fast w-5 h-5" />
                            NEXUS
                        </h1>
                    </div>
                    <p className="text-[10px] text-slate-500 font-mono pl-9">v2.5.0 HYPER-ANALYTICAL ENGINE</p>
                </div>

                {/* Input Area */}
                <div className="p-4 space-y-4">
                    <div className="relative group">
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && onRefresh()}
                            placeholder="Refine vector..."
                            className="w-full bg-nexus-900 border border-nexus-800 rounded-md py-3 pl-10 pr-4 text-sm font-mono focus:outline-none focus:border-nexus-500 focus:ring-1 focus:ring-nexus-500 transition-all placeholder-slate-600 text-cyan-100 group-hover:border-nexus-700"
                        />
                        <Search className="absolute left-3 top-3.5 w-4 h-4 text-slate-500 group-hover:text-nexus-400 transition-colors" />
                    </div>

                    <button
                        onClick={onRefresh}
                        disabled={state === AnalysisState.INGESTING || state === AnalysisState.CONNECTING || state === AnalysisState.SIMULATING}
                        className="w-full py-3 bg-nexus-500 hover:bg-nexus-400 disabled:bg-nexus-900 disabled:text-slate-500 disabled:cursor-not-allowed text-nexus-950 font-bold font-mono text-sm rounded flex items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(59,130,246,0.3)] hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] active:scale-95"
                    >
                        {state === AnalysisState.IDLE || state === AnalysisState.COMPLETE ? (
                            <>
                                <RefreshCw className="w-4 h-4" /> RE-CALCULATE
                            </>
                        ) : (
                            <>
                                <Activity className="w-4 h-4 animate-spin" /> PROCESSING...
                            </>
                        )}
                    </button>
                </div>

                {/* Active Agents List */}
                <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
                    <h2 className="text-xs font-mono text-slate-500 uppercase tracking-widest mb-4">Active Agents</h2>

                    {[
                        { name: 'ECON_MODEL_X', icon: Database, color: 'text-emerald-400' },
                        { name: 'SOC_SENTIMENT', icon: Globe, color: 'text-blue-400' },
                        { name: 'RISK_ASSESSOR', icon: ShieldAlert, color: 'text-amber-500' },
                        { name: 'POLICY_TRACER', icon: Share2, color: 'text-purple-400' },
                    ].map((agent, i) => (
                        <div key={i} className="flex items-center gap-3 p-3 rounded bg-nexus-900/50 border border-nexus-800/50 hover:bg-nexus-900 transition-colors">
                            <agent.icon className={`w-4 h-4 ${agent.color}`} />
                            <div className="flex-1">
                                <div className="text-xs font-mono font-bold text-slate-300">{agent.name}</div>
                                <div className="text-[10px] text-slate-500 flex items-center gap-1">
                                    <span className={`w-1.5 h-1.5 rounded-full ${state === AnalysisState.IDLE || state === AnalysisState.COMPLETE ? 'bg-slate-600' : 'bg-green-500 animate-pulse'}`}></span>
                                    {state === AnalysisState.IDLE || state === AnalysisState.COMPLETE ? 'STANDBY' : 'PROCESSING'}
                                </div>
                            </div>
                            <div className="text-[10px] font-mono text-slate-600">v{2 + i}.0</div>
                        </div>
                    ))}
                </div>

                {/* System Status Footer */}
                <div className="p-3 border-t border-nexus-800 bg-nexus-950 text-[10px] font-mono text-slate-500 flex justify-between">
                    <span>RAM: 64TB</span>
                    <span>LATENCY: 12ms</span>
                    <span className="text-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]">ONLINE</span>
                </div>
            </div>

            {/* CENTER - VISUALIZATION & OUTPUT */}
            <div className="flex-1 flex flex-col relative grid-bg">

                {/* Top Bar */}
                <div className="h-16 border-b border-nexus-800 bg-nexus-950/90 backdrop-blur flex items-center justify-between px-6 z-10">
                    <div className="flex items-center gap-4">
                        <span className="text-sm font-mono text-slate-400">CURRENT TARGET:</span>
                        <span className="px-3 py-1 bg-nexus-900 border border-nexus-500/30 rounded text-nexus-400 font-mono text-sm shadow-[0_0_10px_rgba(6,182,212,0.1)] truncate max-w-md">
                            {query || 'NO_TARGET_SELECTED'}
                        </span>
                    </div>
                    <div className="flex gap-6 text-xs font-mono text-slate-500">
                        <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-nexus-500" />
                            <span>NODES: <span className="text-slate-300">{simulationData.nodes.length}</span></span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Share2 className="w-4 h-4 text-nexus-500" />
                            <span>LINKS: <span className="text-slate-300">{simulationData.links.length}</span></span>
                        </div>
                    </div>
                </div>

                {/* Main Content Area */}
                <div className="flex-1 flex overflow-hidden">

                    {/* Graph Visualization */}
                    <div className="flex-1 relative" ref={graphContainerRef}>
                        <NetworkGraph
                            nodes={simulationData.nodes}
                            links={simulationData.links}
                            width={containerDimensions.width}
                            height={containerDimensions.height}
                            onNodeClick={handleNodeClick}
                        />

                        {/* Floating Analysis Summary (Only visible if no node selected) */}
                        {state === AnalysisState.COMPLETE && !selectedNode && (
                            <div className="absolute bottom-6 left-6 right-6 max-w-3xl bg-nexus-950/80 backdrop-blur-md border border-nexus-700/60 p-5 rounded-lg shadow-2xl animate-in slide-in-from-bottom-10 fade-in duration-700 z-20 pointer-events-none">
                                <div className="flex items-start gap-4">
                                    <div className="p-2 bg-nexus-900 rounded-lg border border-nexus-800">
                                        <Terminal className="w-5 h-5 text-nexus-accent" />
                                    </div>
                                    <div>
                                        <h3 className="text-sm font-bold text-slate-200 mb-1 font-mono tracking-wide">EXECUTIVE SYNTHESIS</h3>
                                        <p className="text-sm text-slate-300 leading-relaxed font-light">
                                            {simulationData.summary}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Right Panel: Context Aware (Simulation Overview OR Entity Detail) */}
                    <div className="w-96 border-l border-nexus-800 bg-nexus-950/50 flex flex-col z-10 backdrop-blur-sm transition-all duration-300">
                        {selectedNode ? (
                            <EntityDetailPanel node={selectedNode} onClose={closeDetailPanel} />
                        ) : (
                            <>
                                <div className="h-1/2 p-4 border-b border-nexus-800">
                                    <SimulationCharts data={simulationData} />
                                </div>
                                <div className="h-1/2">
                                    <DataTerminal logs={logs} />
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>

        </div>
    );
};

export default DashboardView;

import React, { useState, useEffect } from 'react';
import {
    Zap,
    Settings,
    Clock,
    Database,
    ChevronDown,
    ChevronUp,
    Cpu,
    Layers,
    Search,
    Upload
} from 'lucide-react';
import { AnalysisConfig } from '../types';
import TypewriterText from './TypewriterText';

interface QueryBuilderPageProps {
    onStart: (query: string, config: AnalysisConfig) => void;
    history: string[];
}

const QueryBuilderPage: React.FC<QueryBuilderPageProps> = ({ onStart, history }) => {
    const [query, setQuery] = useState('');
    const [showConfig, setShowConfig] = useState(false);
    const [config, setConfig] = useState<AnalysisConfig>({
        depth: 'standard',
        focus: { actors: true, policies: true, outcomes: true, risks: true },
        agents: { extractor: true, mapper: true, resolver: true }
    });

    // Animation values
    const [activeValueProp, setActiveValueProp] = useState(0);
    const valueProps = [
        "Map complex relationships across 100s of sources",
        "Extract Actors, Policies, Outcomes & Risks",
        "Multi-agent reasoning with full transparency",
        "Trace every claim to source evidence"
    ];

    useEffect(() => {
        const interval = setInterval(() => {
            setActiveValueProp(prev => (prev + 1) % valueProps.length);
        }, 4000);
        return () => clearInterval(interval);
    }, []);

    const getEstimation = () => {
        if (config.depth === 'quick') return { time: '~2 min', chunks: 15, tokens: '45K', cost: 'Low' };
        if (config.depth === 'deep') return { time: '~20 min', chunks: 150, tokens: '450K', cost: 'High' };
        return { time: '~8 min', chunks: 50, tokens: '150K', cost: 'Med' };
    };
    const est = getEstimation();

    const handleStart = () => {
        if (query.trim()) {
            onStart(query, config);
        }
    };

    return (
        <div className="h-screen w-screen bg-nexus-950 text-slate-200 overflow-hidden font-sans relative flex flex-col items-center justify-center p-6 grid-bg">

            {/* Header */}
            <div className="absolute top-0 left-0 right-0 p-6 flex justify-between items-center z-20">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-nexus-900 border border-nexus-800 flex items-center justify-center text-nexus-accent">
                        <Cpu className="w-5 h-5" />
                    </div>
                    <div>
                        <h1 className="text-xl font-mono font-bold tracking-tighter text-white">NEXUS</h1>
                        <p className="text-[10px] text-slate-500 font-mono tracking-widest">v2.5.0 DEEP ANALYSIS PLATFORM</p>
                    </div>
                </div>
                <div className="flex gap-4 text-xs font-mono text-slate-500">
                    <button className="hover:text-nexus-400 transition-colors">[HISTORY]</button>
                    <button className="hover:text-nexus-400 transition-colors">[SETTINGS]</button>
                </div>
            </div>

            {/* Animated Background Elements */}
            <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
                {/* Central Orbiting Rings */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] border border-nexus-800/30 rounded-full animate-spin-slow"></div>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[450px] h-[450px] border border-nexus-800/20 rounded-full animate-[spin_5s_linear_infinite_reverse]"></div>

                {/* Floating Nodes */}
                <div className="absolute top-1/4 left-1/4 w-3 h-3 bg-blue-500/20 rounded-full animate-pulse shadow-[0_0_15px_rgba(59,130,246,0.5)]"></div>
                <div className="absolute bottom-1/3 right-1/4 w-4 h-4 bg-purple-500/20 rounded-full animate-pulse delay-700 shadow-[0_0_15px_rgba(168,85,247,0.5)]"></div>
                <div className="absolute top-1/3 right-1/3 w-2 h-2 bg-emerald-500/20 rounded-full animate-pulse delay-300 shadow-[0_0_15px_rgba(16,185,129,0.5)]"></div>
            </div>

            {/* Main Content Container */}
            <div className="w-full max-w-2xl relative z-10 flex flex-col gap-8">

                {/* Animated Hero Text */}
                <div className="text-center space-y-2 h-24 flex flex-col items-center justify-center">
                    <div className="flex items-center gap-3 mb-2">
                        <span className="w-2 h-2 bg-nexus-accent rounded-full animate-pulse"></span>
                        <span className="w-2 h-2 bg-nexus-accent rounded-full animate-pulse delay-100"></span>
                        <span className="w-2 h-2 bg-nexus-accent rounded-full animate-pulse delay-200"></span>
                    </div>
                    <div className="text-lg font-mono text-nexus-400 min-h-[2rem]">
                        <TypewriterText
                            key={activeValueProp}
                            text={valueProps[activeValueProp]}
                            speed={30}
                        />
                    </div>
                </div>

                {/* Query Input Box */}
                <div className="bg-nexus-900/80 backdrop-blur-xl border border-nexus-700 rounded-lg shadow-2xl overflow-hidden group focus-within:border-nexus-500 transition-colors">
                    <div className="p-1">
                        <div className="relative">
                            <textarea
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                placeholder="What do you want to analyze? e.g. China's semiconductor policy impact..."
                                className="w-full bg-nexus-950/50 text-slate-200 p-4 pl-12 h-32 resize-none focus:outline-none font-mono text-sm leading-relaxed custom-scrollbar placeholder-slate-600"
                            />
                            <Search className="absolute left-4 top-4 w-5 h-5 text-slate-500 group-focus-within:text-nexus-400 transition-colors" />

                            <button className="absolute bottom-3 right-3 text-xs flex items-center gap-2 px-3 py-1.5 bg-nexus-800 hover:bg-nexus-700 rounded text-slate-400 border border-nexus-700 transition-all">
                                <Upload className="w-3 h-3" /> Source Text
                            </button>
                        </div>
                    </div>

                    {/* Advanced Configuration Toggle */}
                    <div className="border-t border-nexus-800">
                        <button
                            onClick={() => setShowConfig(!showConfig)}
                            className="w-full px-4 py-2 flex items-center justify-between text-xs font-mono text-slate-500 hover:text-nexus-400 hover:bg-nexus-900/50 transition-colors"
                        >
                            <span className="flex items-center gap-2">
                                <Settings className="w-3 h-3" /> ADVANCED CONFIGURATION
                            </span>
                            {showConfig ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>

                        {showConfig && (
                            <div className="p-4 bg-nexus-950/30 border-t border-nexus-800 animate-in slide-in-from-top-2 duration-200">
                                <div className="grid grid-cols-2 gap-8">

                                    {/* Column 1 */}
                                    <div className="space-y-4">
                                        <div>
                                            <label className="text-[10px] text-slate-500 uppercase tracking-widest font-mono mb-2 block">Analysis Depth</label>
                                            <div className="flex flex-col gap-2">
                                                {(['quick', 'standard', 'deep'] as const).map(depth => (
                                                    <label key={depth} className="flex items-center gap-2 cursor-pointer group">
                                                        <div className={`w-3 h-3 rounded-full border flex items-center justify-center ${config.depth === depth ? 'border-nexus-accent' : 'border-slate-600'}`}>
                                                            {config.depth === depth && <div className="w-1.5 h-1.5 rounded-full bg-nexus-accent"></div>}
                                                        </div>
                                                        <input
                                                            type="radio"
                                                            name="depth"
                                                            className="hidden"
                                                            checked={config.depth === depth}
                                                            onChange={() => setConfig({ ...config, depth })}
                                                        />
                                                        <span className={`text-xs font-mono uppercase ${config.depth === depth ? 'text-slate-200' : 'text-slate-500 group-hover:text-slate-400'}`}>{depth}</span>
                                                    </label>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Column 2 */}
                                    <div className="space-y-4">
                                        <div>
                                            <label className="text-[10px] text-slate-500 uppercase tracking-widest font-mono mb-2 block">APOR Focus</label>
                                            <div className="grid grid-cols-2 gap-2">
                                                {Object.entries(config.focus).map(([key, value]) => (
                                                    <label key={key} className="flex items-center gap-2 cursor-pointer group">
                                                        <div className={`w-3 h-3 rounded border flex items-center justify-center ${value ? 'bg-nexus-500/20 border-nexus-500' : 'border-slate-600'}`}>
                                                            {value && <div className="w-1.5 h-1.5 bg-nexus-500"></div>}
                                                        </div>
                                                        <input
                                                            type="checkbox"
                                                            className="hidden"
                                                            checked={value}
                                                            onChange={() => setConfig({
                                                                ...config,
                                                                focus: { ...config.focus, [key]: !value }
                                                            })}
                                                        />
                                                        <span className={`text-xs font-mono capitalize ${value ? 'text-slate-200' : 'text-slate-500'}`}>{key}</span>
                                                    </label>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Estimation & Action */}
                <div className="flex items-center gap-4">
                    <div className="flex-1 p-3 bg-nexus-900/50 border border-nexus-800 rounded flex justify-between text-xs font-mono text-slate-400">
                        <div className="flex items-center gap-2">
                            <Clock className="w-3 h-3 text-nexus-500" /> {est.time}
                        </div>
                        <div className="flex items-center gap-2">
                            <Database className="w-3 h-3 text-nexus-500" /> {est.chunks} chunks
                        </div>
                        <div className="flex items-center gap-2">
                            <Layers className="w-3 h-3 text-nexus-500" /> {est.tokens}
                        </div>
                    </div>

                    <button
                        onClick={handleStart}
                        disabled={!query.trim()}
                        className="px-8 py-3 bg-nexus-500 hover:bg-nexus-400 disabled:bg-nexus-900 disabled:text-slate-600 disabled:border-nexus-800 text-nexus-950 font-bold font-mono text-sm rounded shadow-[0_0_20px_rgba(59,130,246,0.4)] hover:shadow-[0_0_30px_rgba(59,130,246,0.6)] transition-all active:scale-95 flex items-center gap-2 whitespace-nowrap"
                    >
                        <Zap className="w-4 h-4 fill-current" /> INITIATE ANALYSIS
                    </button>
                </div>

                {/* Recent Analyses */}
                <div className="mt-8">
                    <p className="text-[10px] text-slate-600 font-mono uppercase tracking-widest mb-3 text-center">Recent Intelligence Vectors</p>
                    <div className="flex justify-center gap-2 flex-wrap">
                        {history.length > 0 ? history.map((item, i) => (
                            <button key={i} onClick={() => setQuery(item)} className="px-3 py-1 bg-nexus-900/40 border border-nexus-800 hover:border-nexus-600 rounded text-xs font-mono text-slate-400 hover:text-nexus-300 transition-colors">
                                {item.length > 30 ? item.substring(0, 30) + '...' : item}
                            </button>
                        )) : (
                            ['EU AI Act Compliance', 'OPEC Strategy 2025', 'South China Sea Logistics'].map((item, i) => (
                                <button key={i} onClick={() => setQuery(item)} className="px-3 py-1 bg-nexus-900/40 border border-nexus-800 hover:border-nexus-600 rounded text-xs font-mono text-slate-400 hover:text-nexus-300 transition-colors">
                                    {item}
                                </button>
                            ))
                        )}
                    </div>
                </div>

            </div>
        </div>
    );
};

export default QueryBuilderPage;

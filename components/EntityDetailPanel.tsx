
import React, { useState, useEffect } from 'react';
import { PolicyNode, EntityConnectionsResponse, AnalysisSummaryResponse } from '../types';
import { X, ShieldAlert, Users, FileText, Activity, Lock, ExternalLink, Calendar, ChevronDown, ChevronRight, BarChart } from 'lucide-react';
import TypewriterText from './TypewriterText';
import ConnectionsDisplay from './ConnectionsDisplay';
import SummaryConfigPanel from './SummaryConfigPanel';
import AnalysisSummary from './AnalysisSummary';

interface EntityDetailPanelProps {
  node: PolicyNode | null;
  onClose: () => void;
  analysisId?: string;
}

const EntityDetailPanel: React.FC<EntityDetailPanelProps> = ({ node, onClose, analysisId }) => {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [connections, setConnections] = useState<EntityConnectionsResponse | null>(null);
  const [generatedSummary, setGeneratedSummary] = useState<AnalysisSummaryResponse | null>(null);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [isLoadingConnections, setIsLoadingConnections] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch connections when node changes
  useEffect(() => {
    if (!node) {
      setConnections(null);
      setGeneratedSummary(null);
      setError(null);
      return;
    }

    const fetchConnections = async () => {
      setIsLoadingConnections(true);
      setError(null);

      try {
        const response = await fetch(`http://localhost:8000/api/entities/${node.id}/connections`);
        if (!response.ok) {
          throw new Error('Failed to fetch connections');
        }
        const data: EntityConnectionsResponse = await response.json();
        setConnections(data);
      } catch (err) {
        console.error('Error fetching connections:', err);
        setError('Failed to load connections');
      } finally {
        setIsLoadingConnections(false);
      }
    };

    fetchConnections();
  }, [node]);

  const handleGenerateSummary = async (selectedTypes: Array<'actor' | 'policy' | 'outcome' | 'risk'>) => {
    if (!node || !analysisId) return;

    setIsGeneratingSummary(true);
    setError(null);

    try {
      const response = await fetch(`http://localhost:8000/api/entities/${node.id}/summary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          selected_types: selectedTypes,
          analysis_id: analysisId,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate summary');
      }

      const data: AnalysisSummaryResponse = await response.json();
      setGeneratedSummary(data);
    } catch (err) {
      console.error('Error generating summary:', err);
      setError('Failed to generate summary');
    } finally {
      setIsGeneratingSummary(false);
    }
  };

  if (!node) return null;

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'actor': return <Users className="w-6 h-6 text-blue-400" />;
      case 'policy': return <FileText className="w-6 h-6 text-purple-400" />;
      case 'outcome': return <Activity className="w-6 h-6 text-emerald-400" />;
      case 'risk': return <ShieldAlert className="w-6 h-6 text-red-500" />;
      default: return <Lock className="w-6 h-6 text-slate-400" />;
    }
  };

  const getHeaderColor = (type: string) => {
    switch (type) {
      case 'actor': return 'border-blue-500/50 bg-blue-950/30';
      case 'policy': return 'border-purple-500/50 bg-purple-950/30';
      case 'outcome': return 'border-emerald-500/50 bg-emerald-950/30';
      case 'risk': return 'border-red-500/50 bg-red-950/30';
      default: return 'border-slate-500/50 bg-slate-950/30';
    }
  };

  const getConfidenceColor = (val: number) => {
      if (val >= 80) return 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]';
      if (val >= 50) return 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]';
      return 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]';
  }

  return (
    <div className="h-full w-full flex flex-col bg-nexus-950/95 backdrop-blur-xl border-l border-nexus-800 animate-in slide-in-from-right duration-500 relative overflow-hidden shadow-2xl">

      {/* Decorative Grid Background */}
      <div className="absolute inset-0 grid-bg opacity-30 pointer-events-none"></div>

      {/* Header */}
      <div className={`p-6 border-b ${getHeaderColor(node.type)} flex items-center justify-between relative z-10`}>
        <div className="flex items-center gap-4">
          <div className="p-3 bg-nexus-900 rounded-lg border border-nexus-700 shadow-xl">
             {getTypeIcon(node.type)}
          </div>
          <div>
            <div className="text-[10px] font-mono text-slate-400 uppercase tracking-widest mb-1">
                APOR // {node.type}
            </div>
            <h2 className="text-xl font-bold font-mono text-slate-100 tracking-tight neon-text leading-tight">
              {node.label}
            </h2>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-nexus-800 rounded-full transition-colors text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-6 overflow-y-auto custom-scrollbar relative z-10">

        {/* Confidence & Dates Row */}
        <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="col-span-2 bg-nexus-900/40 border border-nexus-800 p-3 rounded-lg">
                <div className="flex justify-between items-center mb-2">
                    <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                        <BarChart className="w-3 h-3" /> CONFIDENCE SCORE
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-200">{node.confidence}%</span>
                </div>
                <div className="w-full h-1.5 bg-nexus-950 rounded-full overflow-hidden">
                    <div
                        className={`h-full ${getConfidenceColor(node.confidence)} transition-all duration-1000`}
                        style={{ width: `${node.confidence}%` }}
                    ></div>
                </div>
            </div>

            <div className="bg-nexus-900/40 border border-nexus-800 p-3 rounded-lg flex flex-col justify-center">
                <span className="text-[10px] text-slate-500 font-mono mb-1 flex items-center gap-1">
                     <Calendar className="w-3 h-3" /> FIRST SEEN
                </span>
                <span className="text-xs text-slate-300 font-mono">{node.firstSeen}</span>
            </div>
            <div className="bg-nexus-900/40 border border-nexus-800 p-3 rounded-lg flex flex-col justify-center">
                <span className="text-[10px] text-slate-500 font-mono mb-1 flex items-center gap-1">
                    <Activity className="w-3 h-3" /> LAST VERIFIED
                </span>
                <span className="text-xs text-slate-300 font-mono">{node.lastSeen}</span>
            </div>
        </div>

        {/* Connections Display */}
        {isLoadingConnections ? (
          <div className="mb-6">
            <div className="bg-nexus-900/60 border border-nexus-800 rounded-lg p-4">
              <div className="flex items-center justify-center py-4">
                <div className="w-6 h-6 border-2 border-nexus-500 border-t-transparent rounded-full animate-spin" />
              </div>
            </div>
          </div>
        ) : connections ? (
          <ConnectionsDisplay connections={connections} />
        ) : error ? (
          <div className="mb-6">
            <div className="bg-nexus-900/60 border border-red-900/50 rounded-lg p-4">
              <p className="text-xs text-red-400 font-mono text-center">{error}</p>
            </div>
          </div>
        ) : null}

        {/* Analysis Summary Configuration */}
        {connections && analysisId && (
          <SummaryConfigPanel
            connections={connections}
            onGenerate={handleGenerateSummary}
            isGenerating={isGeneratingSummary}
          />
        )}

        {/* Generated Analysis Summary */}
        {(isGeneratingSummary || generatedSummary) && (
          <AnalysisSummary
            summary={generatedSummary}
            isLoading={isGeneratingSummary}
          />
        )}

        {/* Original Entity Summary (fallback) */}
        {!generatedSummary && !isGeneratingSummary && (
          <div className="mb-6">
              <h3 className="text-xs font-mono text-nexus-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                  <span className="w-2 h-2 bg-nexus-400 rounded-full animate-pulse"></span>
                  Entity Summary
              </h3>
              <div className="p-5 rounded-xl bg-nexus-900/60 border border-nexus-800 shadow-inner font-mono text-sm leading-relaxed text-slate-300">
                  <TypewriterText text={node.summary || "No intelligence data available for this node."} speed={15} />
              </div>
          </div>
        )}

        {/* Sources Dropdown */}
        <div className="border border-nexus-800 rounded-lg bg-nexus-900/30 overflow-hidden mb-6">
            <button
                onClick={() => setSourcesExpanded(!sourcesExpanded)}
                className="w-full flex items-center justify-between p-3 hover:bg-nexus-800/50 transition-colors"
            >
                <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                    <FileText className="w-3 h-3" />
                    <span>SOURCES ({node.sources?.length || 0})</span>
                </div>
                {sourcesExpanded ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
            </button>

            {sourcesExpanded && (
                <div className="border-t border-nexus-800 p-3 bg-nexus-950/50">
                    {node.sources && node.sources.length > 0 ? (
                        <ul className="space-y-2">
                            {node.sources.map((source, idx) => (
                                <li key={idx} className="flex items-start gap-2 group cursor-pointer">
                                    <ExternalLink className="w-3 h-3 text-nexus-500 mt-0.5 flex-shrink-0 group-hover:text-nexus-400" />
                                    <span className="text-xs text-slate-400 font-mono group-hover:text-nexus-300 transition-colors underline-offset-4 group-hover:underline">
                                        {source}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="text-xs text-slate-600 font-mono italic p-2">No attribution data linked.</div>
                    )}
                </div>
            )}
        </div>

        {/* Metadata / Footer details */}
        <div className="border-t border-nexus-800/50 pt-6">
             <div className="grid grid-cols-2 gap-4 text-xs font-mono text-slate-500">
                 <div>
                     <span className="block text-slate-600 mb-1">ENTITY ID</span>
                     <span className="text-slate-400">{node.id.toUpperCase()}</span>
                 </div>
                 <div>
                     <span className="block text-slate-600 mb-1">IMPACT FACTOR</span>
                     <span className="text-nexus-accent">{node.impactScore}/100</span>
                 </div>
             </div>

             <button className="w-full mt-6 py-2 border border-nexus-500/30 rounded text-nexus-400 font-mono text-xs hover:bg-nexus-500/10 transition-colors flex items-center justify-center gap-2">
                <ExternalLink className="w-3 h-3" /> OPEN FULL DOSSIER
             </button>
        </div>
      </div>
    </div>
  );
};

export default EntityDetailPanel;

import React, { useState } from 'react';
import { EntityConnectionsResponse } from '../types';
import { Users, FileText, Activity, ShieldAlert, Check } from 'lucide-react';

interface SummaryConfigPanelProps {
  connections: EntityConnectionsResponse;
  onGenerate: (selectedTypes: Array<'actor' | 'policy' | 'outcome' | 'risk'>) => void;
  isGenerating?: boolean;
}

const SummaryConfigPanel: React.FC<SummaryConfigPanelProps> = ({
  connections,
  onGenerate,
  isGenerating = false
}) => {
  const [selectedTypes, setSelectedTypes] = useState<Set<'actor' | 'policy' | 'outcome' | 'risk'>>(new Set());

  const aporConfig: Array<{
    key: 'actor' | 'policy' | 'outcome' | 'risk';
    label: string;
    plural: 'actors' | 'policies' | 'outcomes' | 'risks';
    color: string;
    icon: React.ElementType;
  }> = [
    { key: 'actor', label: 'ACTOR', plural: 'actors', color: 'text-blue-400', icon: Users },
    { key: 'policy', label: 'POLICY', plural: 'policies', color: 'text-purple-400', icon: FileText },
    { key: 'outcome', label: 'OUTCOME', plural: 'outcomes', color: 'text-emerald-400', icon: Activity },
    { key: 'risk', label: 'RISK', plural: 'risks', color: 'text-red-500', icon: ShieldAlert },
  ];

  const toggleType = (type: 'actor' | 'policy' | 'outcome' | 'risk') => {
    const newSelected = new Set(selectedTypes);
    if (newSelected.has(type)) {
      newSelected.delete(type);
    } else {
      newSelected.add(type);
    }
    setSelectedTypes(newSelected);
  };

  const handleGenerate = () => {
    if (selectedTypes.size > 0) {
      onGenerate(Array.from(selectedTypes));
    }
  };

  const getConnectionCount = (plural: 'actors' | 'policies' | 'outcomes' | 'risks'): number => {
    return connections.connections[plural]?.count || 0;
  };

  const canGenerate = selectedTypes.size > 0 && !isGenerating;

  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] text-slate-400 font-mono uppercase tracking-widest">
          Analysis Summary Configuration
        </span>
      </div>

      <div className="bg-nexus-900/60 border border-nexus-800 rounded-lg p-4">
        <div className="space-y-2 mb-4">
          {aporConfig.map((config) => {
            const count = getConnectionCount(config.plural);
            const isSelected = selectedTypes.has(config.key);
            const isDisabled = count === 0;
            const Icon = config.icon;

            return (
              <button
                key={config.key}
                onClick={() => !isDisabled && toggleType(config.key)}
                disabled={isDisabled}
                className={`
                  w-full flex items-center justify-between p-3 rounded border transition-all
                  ${isDisabled
                    ? 'border-nexus-800/50 bg-nexus-900/30 opacity-40 cursor-not-allowed'
                    : isSelected
                      ? 'border-nexus-500/50 bg-nexus-800/80'
                      : 'border-nexus-700/50 bg-nexus-900/40 hover:border-nexus-600 hover:bg-nexus-800/60'
                  }
                `}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-1.5 rounded ${isSelected ? 'bg-nexus-700/50' : 'bg-nexus-800/50'}`}>
                    <Icon className={`w-4 h-4 ${config.color}`} />
                  </div>
                  <div className="text-left">
                    <div className={`text-xs font-mono font-semibold ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                      {config.label}
                    </div>
                    <div className={`text-[9px] font-mono ${isDisabled ? 'text-slate-600' : 'text-slate-500'}`}>
                      {isDisabled ? 'No connections' : `${count} connected`}
                    </div>
                  </div>
                </div>

                {isSelected && (
                  <div className="p-1 rounded-full bg-nexus-500/20 border border-nexus-500/30">
                    <Check className="w-3 h-3 text-nexus-400" />
                  </div>
                )}
              </button>
            );
          })}
        </div>

        <button
          onClick={handleGenerate}
          disabled={!canGenerate}
          className={`
            w-full py-2.5 rounded font-mono text-xs font-bold transition-all flex items-center justify-center gap-2
            ${canGenerate
              ? 'bg-nexus-500 hover:bg-nexus-400 text-nexus-950 shadow-[0_0_15px_rgba(59,130,246,0.3)] hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] active:scale-95'
              : 'bg-nexus-900/50 text-slate-600 cursor-not-allowed border border-nexus-800'
            }
          `}
        >
          {isGenerating ? (
            <>
              <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
              GENERATING...
            </>
          ) : (
            <>GENERATE SUMMARY</>
          )}
        </button>

        {selectedTypes.size === 0 && (
          <div className="mt-2 text-center">
            <span className="text-[9px] text-slate-600 font-mono">Select at least one connection type</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default SummaryConfigPanel;

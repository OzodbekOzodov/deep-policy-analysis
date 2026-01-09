import React from 'react';
import { EntityConnectionsResponse } from '../types';
import { Users, FileText, Activity, ShieldAlert } from 'lucide-react';

interface ConnectionsDisplayProps {
  connections: EntityConnectionsResponse;
}

const ConnectionsDisplay: React.FC<ConnectionsDisplayProps> = ({ connections }) => {
  const getTypeColor = (type: string): string => {
    switch (type) {
      case 'actor': return 'text-blue-400';
      case 'policy': return 'text-purple-400';
      case 'outcome': return 'text-emerald-400';
      case 'risk': return 'text-red-500';
      default: return 'text-slate-400';
    }
  };

  const getTypeBgColor = (type: string): string => {
    switch (type) {
      case 'actor': return 'bg-blue-400';
      case 'policy': return 'bg-purple-400';
      case 'outcome': return 'bg-emerald-400';
      case 'risk': return 'bg-red-500';
      default: return 'bg-slate-400';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'actor': return <Users className="w-3.5 h-3.5" />;
      case 'policy': return <FileText className="w-3.5 h-3.5" />;
      case 'outcome': return <Activity className="w-3.5 h-3.5" />;
      case 'risk': return <ShieldAlert className="w-3.5 h-3.5" />;
      default: return null;
    }
  };

  const aporOrder: Array<'actors' | 'policies' | 'outcomes' | 'risks'> = ['actors', 'policies', 'outcomes', 'risks'];

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] text-slate-400 font-mono uppercase tracking-widest">Connections</span>
      </div>
      <div className="bg-nexus-900/60 border border-nexus-800 rounded-lg p-3">
        <div className="grid grid-cols-4 gap-2">
          {aporOrder.map((key) => {
            const count = connections.connections[key]?.count || 0;
            const type = key.slice(0, -1) as 'actor' | 'policy' | 'outcome' | 'risk';
            const hasConnections = count > 0;

            return (
              <div
                key={key}
                className={`flex flex-col items-center justify-center p-2 rounded border transition-all ${
                  hasConnections
                    ? 'border-nexus-700 bg-nexus-800/50'
                    : 'border-transparent bg-nexus-900/30 opacity-40'
                }`}
              >
                <div className={`flex items-center gap-1.5 ${getTypeColor(type)}`}>
                  {getTypeIcon(type)}
                  <span className="text-lg font-bold font-mono">{count}</span>
                </div>
                <span className={`text-[9px] font-mono uppercase mt-1 ${
                  hasConnections ? 'text-slate-400' : 'text-slate-600'
                }`}>
                  {key.slice(0, 1).toUpperCase()}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ConnectionsDisplay;

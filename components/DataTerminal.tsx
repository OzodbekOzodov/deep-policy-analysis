import React, { useEffect, useRef, useState } from 'react';
import { AgentLog } from '../types';

interface DataTerminalProps {
  logs: AgentLog[];
}

const DataTerminal: React.FC<DataTerminalProps> = ({ logs }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="flex flex-col h-full bg-nexus-950 font-mono text-xs border-t border-nexus-800">
      <div className="flex items-center justify-between px-3 py-1 bg-nexus-900 border-b border-nexus-800">
        <span className="text-nexus-400">SYSTEM.LOG</span>
        <div className="flex gap-1">
          <div className="w-2 h-2 rounded-full bg-red-500"></div>
          <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
          <div className="w-2 h-2 rounded-full bg-green-500"></div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
        {logs.map((log) => (
          <div key={log.id} className="flex gap-2 opacity-80 hover:opacity-100 transition-opacity">
            <span className="text-slate-500">[{log.timestamp}]</span>
            <span className={`
              ${log.status === 'scanning' ? 'text-blue-400' : ''}
              ${log.status === 'connecting' ? 'text-purple-400' : ''}
              ${log.status === 'simulating' ? 'text-emerald-400' : ''}
              ${log.status === 'idle' ? 'text-slate-400' : ''}
              font-bold
            `}>
              {log.agentName}
            </span>
            <span className="text-slate-300">::</span>
            <span className="text-slate-200">{log.action}</span>
            <span className="text-nexus-accent"> &lt;{log.target}&gt;</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default DataTerminal;

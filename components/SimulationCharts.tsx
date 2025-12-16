
import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { SimulationData } from '../types';

interface SimulationChartsProps {
  data: SimulationData;
}

const SimulationCharts: React.FC<SimulationChartsProps> = ({ data }) => {
  
  // Guard against missing arrays
  const labels = data.timelineLabels || [];
  const gdp = data.projectedGDP || [];
  const stability = data.socialStability || [];

  const chartData = labels.map((label, index) => ({
    name: label,
    gdp: gdp[index] ?? 0,
    stability: stability[index] ?? 0
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const gdpValue = payload[0]?.value ?? 0;
      const stabilityValue = payload[1]?.value ?? 0;

      return (
        <div className="bg-nexus-900 border border-nexus-800 p-2 rounded shadow-lg backdrop-blur-md">
          <p className="text-slate-300 font-mono text-xs mb-1">{label}</p>
          <p className="text-emerald-400 font-mono text-sm">
            GDP Index: {typeof gdpValue === 'number' ? gdpValue.toFixed(1) : gdpValue}
          </p>
          <p className="text-blue-400 font-mono text-sm">
            Stability: {typeof stabilityValue === 'number' ? stabilityValue.toFixed(1) : stabilityValue}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="h-full flex flex-col gap-4">
       <div className="h-1/2 glass-panel p-4 rounded-xl flex flex-col relative overflow-hidden">
          <div className="absolute top-0 right-0 p-2 opacity-10 pointer-events-none">
              <div className="w-16 h-16 rounded-full bg-emerald-500 blur-2xl"></div>
          </div>
          <h3 className="text-xs font-mono text-slate-400 mb-2 uppercase tracking-widest flex items-center gap-2">
            <span className="w-1 h-3 bg-emerald-500"></span>
            Economic Projection
          </h3>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                <defs>
                    <linearGradient id="colorGdp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#34d399" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#34d399" stopOpacity={0}/>
                    </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} domain={[0, 100]} />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#334155', strokeWidth: 1 }} />
                <Area 
                    type="monotone" 
                    dataKey="gdp" 
                    stroke="#34d399" 
                    fillOpacity={1} 
                    fill="url(#colorGdp)" 
                    strokeWidth={2} 
                    animationDuration={2000}
                />
                </AreaChart>
            </ResponsiveContainer>
          </div>
       </div>

       <div className="h-1/2 glass-panel p-4 rounded-xl flex flex-col relative overflow-hidden">
          <div className="absolute top-0 right-0 p-2 opacity-10 pointer-events-none">
              <div className="w-16 h-16 rounded-full bg-blue-500 blur-2xl"></div>
          </div>
          <h3 className="text-xs font-mono text-slate-400 mb-2 uppercase tracking-widest flex items-center gap-2">
             <span className="w-1 h-3 bg-blue-500"></span>
             Social Stability Matrix
          </h3>
          <div className="flex-1 min-h-0">
             <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                <defs>
                    <linearGradient id="colorStab" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#60a5fa" stopOpacity={0}/>
                    </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} domain={[0, 100]} />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#334155', strokeWidth: 1 }} />
                <Area 
                    type="monotone" 
                    dataKey="stability" 
                    stroke="#60a5fa" 
                    fillOpacity={1} 
                    fill="url(#colorStab)" 
                    strokeWidth={2}
                    animationDuration={2000} 
                />
                </AreaChart>
            </ResponsiveContainer>
          </div>
       </div>
    </div>
  );
};

export default SimulationCharts;

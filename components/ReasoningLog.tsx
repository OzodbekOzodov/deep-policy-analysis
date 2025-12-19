
import React, { useEffect, useRef } from 'react';
import { CheckCircle2, Circle, Loader2, XCircle, BrainCircuit } from 'lucide-react';

export interface ReasoningStep {
    id: string;
    message: string;
    status: 'pending' | 'loading' | 'complete' | 'failed';
    timestamp?: string;
}

interface ReasoningLogProps {
    steps: ReasoningStep[];
}

const ReasoningLog: React.FC<ReasoningLogProps> = ({ steps }) => {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (steps.some(s => s.status === 'loading' || s.status === 'complete')) {
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [steps]);

    return (
        <div className="h-full flex flex-col glass-panel rounded-xl overflow-hidden border border-nexus-800/50 bg-nexus-950/30">
            {/* Header */}
            <div className="p-3 border-b border-nexus-800/50 bg-nexus-900/20 backdrop-blur-sm flex items-center gap-2">
                <BrainCircuit className="w-4 h-4 text-nexus-accent animate-pulse-slow" />
                <h3 className="text-xs font-mono font-bold text-nexus-100/80 uppercase tracking-widest">
                    Reasoning Engine
                </h3>
            </div>

            {/* Steps List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                {steps.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2 opacity-50">
                        <BrainCircuit className="w-8 h-8" />
                        <span className="text-xs font-mono">AWAITING INPUT_</span>
                    </div>
                ) : (
                    steps.map((step) => (
                        <div
                            key={step.id}
                            className={`flex items-start gap-3 text-sm font-mono transition-all duration-300 ${step.status === 'pending' ? 'opacity-40' : 'opacity-100'
                                }`}
                        >
                            <div className="mt-0.5 shrink-0">
                                {step.status === 'loading' && (
                                    <Loader2 className="w-4 h-4 text-nexus-400 animate-spin" />
                                )}
                                {step.status === 'complete' && (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                )}
                                {step.status === 'failed' && (
                                    <XCircle className="w-4 h-4 text-red-500" />
                                )}
                                {step.status === 'pending' && (
                                    <Circle className="w-4 h-4 text-slate-700" />
                                )}
                            </div>

                            <div className="flex flex-col gap-0.5">
                                <span className={`leading-tight ${step.status === 'complete' ? 'text-slate-200' :
                                        step.status === 'loading' ? 'text-nexus-300' :
                                            step.status === 'failed' ? 'text-red-400' :
                                                'text-slate-500'
                                    }`}>
                                    {step.message}
                                </span>
                                {step.timestamp && step.status !== 'pending' && (
                                    <span className="text-[10px] text-slate-600">
                                        {step.timestamp}
                                    </span>
                                )}
                            </div>
                        </div>
                    ))
                )}
                <div ref={bottomRef} />
            </div>
        </div>
    );
};

export default ReasoningLog;

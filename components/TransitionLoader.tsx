import React, { useEffect, useState } from 'react';
import { Cpu, ShieldCheck, Radio, Binary, Database, Lock } from 'lucide-react';

interface TransitionLoaderProps {
    query: string;
    onComplete: () => void;
}

const TransitionLoader: React.FC<TransitionLoaderProps> = ({ query, onComplete }) => {
    const [progress, setProgress] = useState(0);
    const [stage, setStage] = useState(0);

    const steps = [
        { text: "INITIALIZING HEURISTIC CORE...", icon: Cpu },
        { text: "ESTABLISHING SECURE HANDSHAKE...", icon: Lock },
        { text: `LOCKING TARGET VECTOR: ${query.substring(0, 20).toUpperCase()}...`, icon: Radio },
        { text: "ALLOCATING NEURAL SWARMS...", icon: Binary },
        { text: "SYNTHESIZING DATA STREAMS...", icon: Database },
        { text: "ACCESS GRANTED.", icon: ShieldCheck }
    ];

    useEffect(() => {
        // Total duration approx 2500ms
        const totalDuration = 2500;
        const intervalTime = 30;
        const stepsCount = totalDuration / intervalTime;
        let currentStep = 0;

        const timer = setInterval(() => {
            currentStep++;
            const newProgress = Math.min((currentStep / stepsCount) * 100, 100);
            setProgress(newProgress);

            // Calculate which text stage we are in
            const stageIndex = Math.floor((newProgress / 100) * (steps.length - 1));
            setStage(stageIndex);

            if (currentStep >= stepsCount) {
                clearInterval(timer);
                setTimeout(onComplete, 200); // Short pause at 100% before unmounting
            }
        }, intervalTime);

        return () => clearInterval(timer);
    }, [onComplete, steps.length]);

    // Handle case where steps[stage] is undefined (shouldn't happen with math above, but for safety)
    const currentStep = steps[stage] || steps[steps.length - 1];
    const CurrentIcon = currentStep.icon;

    return (
        <div className="fixed inset-0 bg-nexus-950 z-50 flex flex-col items-center justify-center overflow-hidden font-mono cursor-wait">
            {/* Background Grid Animation */}
            <div className="absolute inset-0 grid-bg opacity-20 animate-pulse"></div>

            {/* Central Content */}
            <div className="relative z-10 w-full max-w-md p-8 flex flex-col items-center gap-8">

                {/* Animated Icon Container */}
                <div className="relative">
                    <div className="absolute inset-0 bg-nexus-accent/20 blur-xl rounded-full animate-pulse"></div>
                    <div className="w-24 h-24 border border-nexus-800 bg-nexus-900/50 rounded-full flex items-center justify-center relative overflow-hidden ring-1 ring-nexus-700 shadow-2xl">
                        <div className="absolute inset-0 border-t-2 border-nexus-accent animate-spin"></div>
                        <CurrentIcon className="w-10 h-10 text-nexus-400 animate-pulse-fast" />
                    </div>
                </div>

                {/* Text & Progress */}
                <div className="w-full space-y-2">
                    <div className="h-6 flex items-center justify-center">
                        <span className="text-nexus-400 text-sm font-bold tracking-widest animate-pulse">
                            {currentStep.text}
                        </span>
                    </div>

                    {/* Progress Bar Container */}
                    <div className="h-1 w-full bg-nexus-900 border border-nexus-800 rounded-full overflow-hidden relative">
                        <div
                            className="h-full bg-gradient-to-r from-nexus-500 to-nexus-accent transition-all duration-75 ease-out shadow-[0_0_10px_rgba(6,182,212,0.8)]"
                            style={{ width: `${progress}%` }}
                        ></div>
                    </div>

                    <div className="flex justify-between text-[10px] text-slate-600">
                        <span>SYSTEM_INTEGRITY: NORMAL</span>
                        <span>{Math.round(progress)}%</span>
                    </div>
                </div>
            </div>

            {/* Decorative Corners */}
            <div className="absolute top-0 left-0 p-8">
                <div className="w-16 h-16 border-t border-l border-nexus-700/50 rounded-tl-3xl"></div>
            </div>
            <div className="absolute bottom-0 right-0 p-8">
                <div className="w-16 h-16 border-b border-r border-nexus-700/50 rounded-br-3xl"></div>
            </div>

            {/* Fast Scrolling Matrix-like Background Text (Low opacity) */}
            <div className="absolute top-0 right-0 h-full w-64 overflow-hidden opacity-5 pointer-events-none hidden md:block">
                <div className="text-[8px] leading-3 text-nexus-accent text-right p-4 whitespace-pre-wrap">
                    {Array(50).fill(0).map((_, i) => (
                        `0x${Math.random().toString(16).substr(2, 8).toUpperCase()} :: ACCESS_REQ\n`
                    ))}
                </div>
            </div>

        </div>
    );
};

export default TransitionLoader;

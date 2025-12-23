import React, { useState, useEffect, useRef, useCallback } from 'react';
import QueryBuilderPage from './components/QueryBuilderPage';
import DashboardView from './components/DashboardView';
import TransitionLoader from './components/TransitionLoader';
import { createAnalysis, pollUntilComplete, getGraph, expandQuery } from './services/api';
import { SimulationData, AgentLog, AnalysisState, PolicyNode, PolicyLink, AnalysisConfig } from './types';

// Mock initial data
const INITIAL_NODES: PolicyNode[] = [];
const INITIAL_LINKS: PolicyLink[] = [];

const INITIAL_SIMULATION: SimulationData = {
  nodes: INITIAL_NODES,
  links: INITIAL_LINKS,
  summary: "Awaiting operator input.",
  projectedGDP: [0, 0, 0, 0, 0],
  socialStability: [100, 100, 100, 100, 100],
  timelineLabels: ["T-0", "T+1", "T+2", "T+3", "T+4"]
};

function App() {
  // Navigation State
  const [view, setView] = useState<'query_builder' | 'transition' | 'dashboard'>('query_builder');

  // Data State
  const [query, setQuery] = useState('');
  const [simulationData, setSimulationData] = useState<SimulationData>(INITIAL_SIMULATION);
  const [state, setState] = useState<AnalysisState>(AnalysisState.IDLE);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [history, setHistory] = useState<string[]>([]);

  // Refs for cleanup and mounting status
  const isMounted = useRef(true);
  const timeoutRefs = useRef<any[]>([]);

  // Cleanup on unmount
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      timeoutRefs.current.forEach(clearTimeout);
    };
  }, []);

  const clearAllTimeouts = () => {
    timeoutRefs.current.forEach(clearTimeout);
    timeoutRefs.current = [];
  };

  // Add log helper
  const addLog = useCallback((agent: string, action: string, target: string, status: AgentLog['status']) => {
    if (!isMounted.current) return;
    const newLog: AgentLog = {
      id: Math.random().toString(36).substr(2, 9),
      agentName: agent,
      action,
      target,
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      status
    };
    setLogs(prev => [...prev.slice(-50), newLog]);
  }, []);

  const runAnalysisSequence = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) return;

    clearAllTimeouts();

    if (isMounted.current) {
      setState(AnalysisState.INGESTING);
      // Clear previous data for a fresh run
      setSimulationData({ ...INITIAL_SIMULATION, summary: "Initializing Neural Handshake..." });
      setLogs([]);
      addLog('SYSTEM', 'INITIATING_SEQUENCE', searchQuery.toUpperCase(), 'scanning');
    }

    try {
      if (isMounted.current) setState(AnalysisState.CONNECTING);

      // 0. Expand query into search variations
      try {
        const expansionResult = await expandQuery(searchQuery, 10);
        if (isMounted.current && expansionResult.expansions.length > 1) {
          addLog('QUERY_EXPANDER', 'QUERY_EXPANDED', `${expansionResult.expansions.length} variations generated`, 'scanning');
          // Log a few example expansions (limit to 3 for UI cleanliness)
          const sampleExpansions = expansionResult.expansions.slice(1, 4);
          sampleExpansions.forEach((exp, idx) => {
            addLog('QUERY_EXPANDER', `VARIANT_${idx + 1}`, exp, 'scanning');
          });
          if (expansionResult.cached) {
            addLog('QUERY_EXPANDER', 'CACHE_HIT', 'Using cached expansions', 'idle');
          }
        }
      } catch (expansionError) {
        // Non-fatal: continue without expansions
        console.warn('Query expansion failed:', expansionError);
      }

      // 1. Create Analysis via Real API
      const { id } = await createAnalysis({ query: searchQuery });
      if (isMounted.current) addLog('DPA', 'JOB_CREATED', `ID: ${id.substring(0, 8)}`, 'scanning');

      // 2. Poll for completion
      await pollUntilComplete(id, (status, stage) => {
        // Optional: update detail status if needed
      });

      if (isMounted.current) {
        addLog('NEXUS_CORE', 'GENERATING_GRAPH', 'Node synthesis complete', 'simulating');
        setState(AnalysisState.SIMULATING);
      }

      // 3. Fetch Graph Results
      const graphData = await getGraph(id);

      if (!isMounted.current) return;

      // Map API response to UI types
      const uiNodes: PolicyNode[] = graphData.nodes.map(n => ({
        id: n.id,
        label: n.label,
        type: n.type,
        impactScore: n.impact_score,
        confidence: n.confidence,
        cluster: n.type === 'actor' ? 0 : n.type === 'policy' ? 1 : n.type === 'outcome' ? 2 : 3,
        summary: n.summary || "No details available.",
        firstSeen: new Date().toISOString().split('T')[0],
        lastSeen: new Date().toISOString().split('T')[0],
        sources: n.provenance.map(p => `Chunk ${p.chunk_id.substring(0, 4)}`)
      }));

      const uiLinks: PolicyLink[] = graphData.links.map(l => ({
        source: l.source,
        target: l.target,
        strength: l.confidence / 10,
        label: l.relationship
      }));

      const finalData: SimulationData = {
        nodes: uiNodes,
        links: uiLinks,
        summary: graphData.summary || "Analysis complete.",
        projectedGDP: graphData.projected_gdp || [50, 50, 50, 50, 50],
        socialStability: graphData.social_stability || [50, 50, 50, 50, 50],
        timelineLabels: graphData.timeline_labels || ["T+1", "T+2", "T+3", "T+4", "T+5"]
      };

      const finalTimeout = setTimeout(() => {
        if (isMounted.current) {
          setSimulationData(finalData);
          setState(AnalysisState.COMPLETE);
          addLog('SYSTEM', 'SEQUENCE_COMPLETE', 'Visualization rendered', 'idle');
        }
      }, 500);
      timeoutRefs.current.push(finalTimeout);

      // Update history
      setHistory(prev => {
        const newHistory = [searchQuery, ...prev.filter(h => h !== searchQuery)].slice(0, 5);
        return newHistory;
      });

    } catch (error) {
      console.error(error);
      if (isMounted.current) {
        const errorMessage = error instanceof Error ? error.message : 'Analysis sequence failed';
        addLog('SYSTEM', 'SEQUENCE_FAILED', errorMessage, 'error');
        setState(AnalysisState.FAILED);
      }
    }
  }, [addLog]);

  const handleStartAnalysis = (newQuery: string, config: AnalysisConfig) => {
    setQuery(newQuery);
    // Step 1: Switch to Transition View
    setView('transition');
  };

  const handleTransitionComplete = () => {
    // Step 2: Switch to Dashboard and start actual logic
    setView('dashboard');
    runAnalysisSequence(query);
  };

  const handleRefresh = () => {
    runAnalysisSequence(query);
  };

  const handleBack = () => {
    setView('query_builder');
    setState(AnalysisState.IDLE);
  };

  return (
    <>
      {view === 'query_builder' && (
        <QueryBuilderPage onStart={handleStartAnalysis} history={history} />
      )}

      {view === 'transition' && (
        <TransitionLoader query={query} onComplete={handleTransitionComplete} />
      )}

      {view === 'dashboard' && (
        <DashboardView
          query={query}
          setQuery={setQuery}
          simulationData={simulationData}
          state={state}
          logs={logs}
          onBack={handleBack}
          onRefresh={handleRefresh}
        />
      )}
    </>
  );
}

export default App;

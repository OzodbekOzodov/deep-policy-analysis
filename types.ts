
export interface PolicyNode {
  id: string;
  label: string;
  type: 'actor' | 'policy' | 'outcome' | 'risk';
  confidence: number; // 0-100
  impactScore: number; // 0-100, affects node size
  cluster: number;
  summary: string; // Detailed background story/analysis
  firstSeen: string; // ISO date
  lastSeen: string; // ISO date
  sources: string[]; // List of source names
}

export interface PolicyLink {
  source: string;
  target: string;
  strength: number;
  label?: string;
}

export interface SimulationData {
  nodes: PolicyNode[];
  links: PolicyLink[];
  summary: string;
  projectedGDP: number[];
  socialStability: number[];
  timelineLabels: string[];
}

export interface AgentLog {
  id: string;
  agentName: string;
  action: string;
  target: string;
  timestamp: string;
  status: 'scanning' | 'connecting' | 'simulating' | 'idle' | 'error';
}

export enum AnalysisState {
  IDLE = 'IDLE',
  INGESTING = 'INGESTING',
  CONNECTING = 'CONNECTING',
  SIMULATING = 'SIMULATING',
  COMPLETE = 'COMPLETE',
  FAILED = 'FAILED'
}

export interface Article {
  id: string;
  title: string;
  source: string; // e.g., "World Bank", "Heritage Foundation"
  bias: number; // -1 to 1
  relevance: number; // 0 to 100
  snippet: string;
}

export interface AnalysisConfig {
  depth: 'quick' | 'standard' | 'deep';
  focus: {
    actors: boolean;
    policies: boolean;
    outcomes: boolean;
    risks: boolean;
  };
  agents: {
    extractor: boolean;
    mapper: boolean;
    resolver: boolean;
  };
}

// ===== Entity Connections & Analysis Summary Types =====

export interface ConnectedEntityInfo {
  id: string;
  label: string;
  type: 'actor' | 'policy' | 'outcome' | 'risk';
  relationship_type: string;
  confidence: number;
}

export interface EntityConnectionsByType {
  count: number;
  entities: ConnectedEntityInfo[];
}

export interface EntityConnectionsResponse {
  entity_id: string;
  entity_label: string;
  entity_type: 'actor' | 'policy' | 'outcome' | 'risk';
  connections: {
    actors: EntityConnectionsByType;
    policies: EntityConnectionsByType;
    outcomes: EntityConnectionsByType;
    risks: EntityConnectionsByType;
  };
}

export interface AnalysisSummaryRequest {
  selected_types: ('actor' | 'policy' | 'outcome' | 'risk')[];
  analysis_id: string;
}

export interface CitationItem {
  id: number;
  text: string;
  chunk_id: string;
  document_title: string | null;
  relationship: string;
  confidence: number;
}

export interface AnalysisSummaryResponse {
  entity_id: string;
  entity_label: string;
  summary: string;
  citations: CitationItem[];
  cache_key: string;
}

export interface EntityProvenanceDetail {
  chunk_id: string;
  quote: string;
  confidence: number;
  chunk_content: string;
  document_title: string;
  document_id: string;
}

export interface EntityProvenanceResponse {
  entity_id: string;
  entity_label: string;
  provenance: EntityProvenanceDetail[];
}

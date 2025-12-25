/**
 * DAP Backend API Client
 * 
 * Connects the React frontend to the FastAPI backend.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** Analysis request parameters */
export interface CreateAnalysisParams {
    query: string;
    text_input?: string;
    scope?: Record<string, unknown>;
    depth?: 'quick' | 'standard' | 'deep';
}

/** Analysis response from backend */
export interface AnalysisResponse {
    id: string;
    query: string;
    status: 'created' | 'processing' | 'complete' | 'failed';
    current_stage: string | null;
    progress: {
        stage: string;
        percent: number;
        stats: {
            actors: number;
            policies: number;
            outcomes: number;
            risks: number;
        };
    } | null;
    created_at: string;
}

/** Entity from graph response */
export interface GraphEntity {
    id: string;
    type: 'actor' | 'policy' | 'outcome' | 'risk';
    label: string;
    confidence: number;
    impact_score: number;
    summary: string | null;
    provenance: Array<{
        chunk_id: string;
        quote: string | null;
        confidence: number;
    }>;
}

/** Relationship from graph response */
export interface GraphRelationship {
    id: string;
    source: string;
    target: string;
    relationship: string;
    confidence: number;
}

/** Graph response from backend */
export interface GraphResponse {
    nodes: GraphEntity[];
    links: GraphRelationship[];
    version: number;
    summary: string | null;
    projected_gdp: number[] | null;
    social_stability: number[] | null;
    timeline_labels: string[] | null;
}

/** SSE progress event */
export interface ProgressEvent {
    type: 'stage_change' | 'stats_update' | 'done' | 'error' | 'timeout';
    stage?: string;
    percent?: number;
    stats?: {
        actors: number;
        policies: number;
        outcomes: number;
        risks: number;
    };
    message?: string;
}

/** Query expansion response */
export interface QueryExpansionResponse {
    original_query: string;
    expansions: string[];
    cached: boolean;
}

/**
 * Create a new analysis
 */
export async function createAnalysis(params: CreateAnalysisParams): Promise<AnalysisResponse> {
    const response = await fetch(`${API_URL}/api/analysis/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
    });

    if (!response.ok) {
        throw new Error(`Failed to create analysis: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Get analysis status
 */
export async function getAnalysis(id: string): Promise<AnalysisResponse> {
    const response = await fetch(`${API_URL}/api/analysis/${id}`);

    if (!response.ok) {
        throw new Error(`Failed to get analysis: ${response.statusText}`);
    }

    return response.json();
}

/**
 * List all analyses (for history)
 */
export async function listAnalyses(options?: {
    limit?: number;
    offset?: number;
    status?: string;
}): Promise<AnalysisResponse[]> {
    const params = new URLSearchParams();
    if (options?.limit) params.append('limit', options.limit.toString());
    if (options?.offset) params.append('offset', options.offset.toString());
    if (options?.status) params.append('status', options.status);

    const response = await fetch(`${API_URL}/api/analysis?${params.toString()}`);

    if (!response.ok) {
        throw new Error(`Failed to list analyses: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Get analysis graph
 */
export async function getGraph(analysisId: string): Promise<GraphResponse> {
    const response = await fetch(`${API_URL}/api/graph/${analysisId}`);

    if (!response.ok) {
        throw new Error(`Failed to get graph: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Expand query into multiple search variations
 */
export async function expandQuery(query: string, numExpansions: number = 15): Promise<QueryExpansionResponse> {
    const response = await fetch(`${API_URL}/api/knowledge/expand`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, num_expansions: numExpansions }),
    });

    if (!response.ok) {
        throw new Error(`Failed to expand query: ${response.statusText}`);
    }

    return response.json();
}

// Polling helper
export async function pollUntilComplete(
    analysisId: string,
    onProgress?: (status: string, stage: string | null) => void,
    interval = 1000
): Promise<AnalysisResponse> {
    while (true) {
        const result = await getAnalysis(analysisId);
        onProgress?.(result.status, result.current_stage);

        if (result.status === 'complete' || result.status === 'failed') {
            return result;
        }
        await new Promise(r => setTimeout(r, interval));
    }
}

/**
 * Stream analysis progress via SSE
 */
export function streamProgress(
    analysisId: string,
    onEvent: (event: ProgressEvent) => void,
    onError?: (error: Error) => void
): EventSource {
    const eventSource = new EventSource(`${API_URL}/api/stream/${analysisId}`);

    eventSource.onmessage = (e) => {
        try {
            const event = JSON.parse(e.data) as ProgressEvent;
            onEvent(event);

            // Close on completion
            if (event.type === 'done' || event.type === 'error' || event.type === 'timeout') {
                eventSource.close();
            }
        } catch (err) {
            console.error('Failed to parse SSE event:', err);
        }
    };

    eventSource.onerror = (e) => {
        console.error('SSE error:', e);
        eventSource.close();
        if (onError) {
            onError(new Error('SSE connection failed'));
        }
    };

    return eventSource;
}

/**
 * Check if backend is healthy
 */
export async function checkHealth(): Promise<boolean> {
    try {
        const response = await fetch(`${API_URL}/health`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.status === 'ok';
    } catch {
        return false;
    }
}


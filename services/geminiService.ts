
import { GoogleGenAI, Type } from "@google/genai";
import { SimulationData } from "../types";

const apiKey = process.env.API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

export const analyzePolicyScenario = async (prompt: string): Promise<SimulationData> => {
  if (!apiKey) {
    throw new Error("API Key not found");
  }

  const model = "gemini-2.5-flash";

  // Calculate dynamic dates for realism
  const today = new Date();
  const oneYearAgo = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate()).toISOString().split('T')[0];
  const currentIso = today.toISOString().split('T')[0];

  const systemInstruction = `
    You are NEXUS, a superintelligence designed for high-dimensional political and economic analysis.
    Your task is to take a user query (a political topic, policy, or region) and generate a complex graph of interconnected nodes representing the systemic implications (APOR Model: Actor, Policy, Outcome, Risk).
    
    CRITICAL: You must return valid JSON that exactly matches the requested schema.
    
    Structure the response to simulate a deep analysis:
    - Nodes: Create 8-15 nodes.
      - 'actor': Key players (Politicians, Agencies, Corporations, Nations).
      - 'policy': Specific bills, regulations, or actions.
      - 'outcome': Economic or social results (GDP, unrest, emissions).
      - 'risk': Potential failures or dangers (War, Crash, Sanctions).
      - summary: A detailed, "insider" background story (2-4 sentences). Explain hidden agendas, historical context, or strategic leverage.
      - confidence: An integer 0-100 representing certainty of data.
      - firstSeen/lastSeen: Realistic dates between ${oneYearAgo} and ${currentIso}.
      - sources: List 1-2 plausible fictional or real source names (e.g., "RAND Corp Report 2024", "CIA World Factbook").
    - Links: Create logical cause-and-effect connections between these nodes.
    - Summary: A professional, high-level executive briefing (2-3 sentences).
    - Data: Realistic projections for GDP and Stability over 5 years relative to the scenario.
  `;

  try {
    const response = await ai.models.generateContent({
      model,
      contents: prompt,
      config: {
        systemInstruction,
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            nodes: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  id: { type: Type.STRING },
                  label: { type: Type.STRING },
                  type: { type: Type.STRING, enum: ['actor', 'policy', 'outcome', 'risk'] },
                  impactScore: { type: Type.NUMBER },
                  confidence: { type: Type.NUMBER },
                  cluster: { type: Type.NUMBER },
                  summary: { type: Type.STRING },
                  firstSeen: { type: Type.STRING },
                  lastSeen: { type: Type.STRING },
                  sources: { type: Type.ARRAY, items: { type: Type.STRING } }
                },
                required: ['id', 'label', 'type', 'impactScore', 'cluster', 'summary', 'confidence', 'firstSeen', 'lastSeen', 'sources']
              }
            },
            links: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  source: { type: Type.STRING },
                  target: { type: Type.STRING },
                  strength: { type: Type.NUMBER },
                  label: { type: Type.STRING },
                },
                required: ['source', 'target', 'strength']
              }
            },
            summary: { type: Type.STRING },
            projectedGDP: { 
              type: Type.ARRAY, 
              items: { type: Type.NUMBER },
              description: "5 data points representing GDP growth index (0-100) over 5 years"
            },
            socialStability: {
              type: Type.ARRAY, 
              items: { type: Type.NUMBER },
              description: "5 data points representing stability index (0-100) over 5 years"
            },
            timelineLabels: {
              type: Type.ARRAY,
              items: { type: Type.STRING },
              description: "Labels for the 5 years (e.g., '2025', '2026')"
            }
          },
          required: ['nodes', 'links', 'summary', 'projectedGDP', 'socialStability', 'timelineLabels']
        }
      }
    });

    const text = response.text;
    if (!text) throw new Error("No response from AI");
    
    const parsedData = JSON.parse(text) as SimulationData;
    
    // Validate and Normalize Data to prevent crashes
    const safeData: SimulationData = {
      nodes: Array.isArray(parsedData.nodes) ? parsedData.nodes : [],
      links: Array.isArray(parsedData.links) ? parsedData.links : [],
      summary: parsedData.summary || "Analysis completed successfully.",
      timelineLabels: Array.isArray(parsedData.timelineLabels) && parsedData.timelineLabels.length > 0 
        ? parsedData.timelineLabels 
        : ["T+1", "T+2", "T+3", "T+4", "T+5"],
      projectedGDP: Array.isArray(parsedData.projectedGDP) ? parsedData.projectedGDP : [],
      socialStability: Array.isArray(parsedData.socialStability) ? parsedData.socialStability : [],
    };

    // Ensure chart arrays match timeline length
    const expectedLength = safeData.timelineLabels.length;
    while (safeData.projectedGDP.length < expectedLength) safeData.projectedGDP.push(50);
    while (safeData.socialStability.length < expectedLength) safeData.socialStability.push(50);
    
    // Trim if too long
    if (safeData.projectedGDP.length > expectedLength) safeData.projectedGDP.length = expectedLength;
    if (safeData.socialStability.length > expectedLength) safeData.socialStability.length = expectedLength;

    return safeData;

  } catch (error) {
    console.error("Analysis Failed", error);
    // Fallback data
    return {
      nodes: [
        { 
          id: '1', label: 'Analysis Failure', type: 'risk', impactScore: 100, cluster: 1, 
          summary: 'System unable to connect to main heuristic core.', confidence: 0, 
          firstSeen: currentIso, lastSeen: currentIso, sources: ['System Logs']
        },
        { 
          id: '2', label: 'Network Error', type: 'policy', impactScore: 50, cluster: 1, 
          summary: 'Check internet connection or API quota limits.', confidence: 0,
          firstSeen: currentIso, lastSeen: currentIso, sources: ['Connectivity Monitor'] 
        }
      ],
      links: [{ source: '1', target: '2', strength: 5, label: 'Error' }],
      summary: "System unable to establish connection to neural core. Please verify API configuration or quota.",
      projectedGDP: [40, 30, 20, 10, 0],
      socialStability: [20, 20, 20, 20, 20],
      timelineLabels: ["ERR", "ERR", "ERR", "ERR", "ERR"]
    };
  }
};

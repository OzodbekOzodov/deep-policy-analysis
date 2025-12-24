"""Query Expansion Prompts and Schema"""

EXPANSION_PROMPT = """You are a research assistant helping to expand a policy research query into multiple search variations.

Original query: "{query}"

Generate {num_expansions} alternative search queries that would help find relevant information. Include:

1. SYNONYM VARIATIONS (3-4): Replace key terms with alternatives
   Example: "China chips" → "China semiconductors", "PRC integrated circuits"

2. ASPECT VARIATIONS (3-4): Break into specific sub-questions
   Example: "China chips" → "China chip manufacturing capacity", "China chip import dependency"

3. ENTITY VARIATIONS (3-4): Add specific named entities likely relevant
   Example: "China chips" → "SMIC production", "Huawei chip supply"

4. TEMPORAL VARIATIONS (2-3): Add time context
   Example: "China chips" → "China semiconductor policy 2024", "recent chip restrictions"

5. RELATIONSHIP VARIATIONS (2-3): Focus on connections between entities
   Example: "China chips" → "US China chip restrictions impact", "Taiwan China semiconductor relations"

Return diverse queries that cover different angles. Each query should be 3-10 words, suitable for semantic search.

Output as JSON with an "expansions" array of strings.
"""

EXPANSION_SCHEMA = {
    "type": "object",
    "properties": {
        "expansions": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["expansions"]
}

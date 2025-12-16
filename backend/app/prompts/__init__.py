"""APOR Entity Extraction Prompts and Schemas"""

# =====================================
# SYSTEM PROMPTS
# =====================================

EXTRACTION_SYSTEM_PROMPT = """You are an expert political and policy analyst specializing in entity extraction.
Your task is to identify and extract entities from text according to the APOR (Actor-Policy-Outcome-Risk) ontology.

Rules:
1. Extract ONLY entities that are explicitly mentioned or strongly implied in the text
2. Provide exact quotes from the text as evidence
3. Assign confidence scores based on how clearly the entity is mentioned
4. Do not hallucinate or infer entities not supported by the text
5. Return valid JSON matching the requested schema"""


# =====================================
# ENTITY EXTRACTION PROMPTS
# =====================================

EXTRACT_ACTORS_PROMPT = """Analyze the following text and extract all ACTORS.

ACTORS are: people, organizations, governments, institutions, agencies, companies, or groups that take actions or make decisions.

Text:
{text}

For each actor found, provide:
- label: Name of the actor
- confidence: 0-100 score (100 = explicitly named, 50 = referenced indirectly)
- quote: Exact text where the actor appears
- aliases: Other names/abbreviations used for this actor in the text

Return JSON with an "entities" array."""


EXTRACT_POLICIES_PROMPT = """Analyze the following text and extract all POLICIES.

POLICIES are: laws, regulations, decisions, agreements, strategies, plans, treaties, orders, or formal actions taken by actors.

Text:
{text}

For each policy found, provide:
- label: Name/description of the policy
- confidence: 0-100 score
- quote: Exact text where the policy is mentioned
- aliases: Other ways this policy is referenced

Return JSON with an "entities" array."""


EXTRACT_OUTCOMES_PROMPT = """Analyze the following text and extract all OUTCOMES.

OUTCOMES are: results, effects, events, measured changes, or consequences that have occurred or are expected to occur due to policies or actions.

Text:
{text}

For each outcome found, provide:
- label: Description of the outcome
- confidence: 0-100 score
- quote: Exact text describing the outcome
- aliases: Other ways this outcome is described

Return JSON with an "entities" array."""


EXTRACT_RISKS_PROMPT = """Analyze the following text and extract all RISKS.

RISKS are: threats, potential negative events, vulnerabilities, dangers, or adverse scenarios mentioned as possibilities.

Text:
{text}

For each risk found, provide:
- label: Description of the risk
- confidence: 0-100 score (100 = explicitly stated risk, 50 = implied concern)
- quote: Exact text mentioning or implying the risk
- aliases: Other ways this risk is described

Return JSON with an "entities" array."""


EXTRACT_RELATIONSHIPS_PROMPT = """Analyze the following text and the entities already extracted to identify RELATIONSHIPS between them.

Entities found:
{entities}

Text:
{text}

For each relationship, provide:
- source: Label of the source entity
- target: Label of the target entity
- relationship: Type of relationship (e.g., "proposes", "implements", "causes", "opposes", "funds", "enables", "blocks", "may_cause")
- confidence: 0-100 score

Return JSON with a "relationships" array."""


# =====================================
# JSON SCHEMAS FOR STRUCTURED OUTPUT
# =====================================

ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Name or description of the entity"
                    },
                    "confidence": {
                        "type": "integer",
                        "description": "Confidence score 0-100"
                    },
                    "quote": {
                        "type": "string",
                        "description": "Exact text from source"
                    },
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alternative names or references"
                    }
                },
                "required": ["label", "confidence", "quote"]
            }
        }
    },
    "required": ["entities"]
}


RELATIONSHIP_SCHEMA = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Label of source entity"
                    },
                    "target": {
                        "type": "string",
                        "description": "Label of target entity"
                    },
                    "relationship": {
                        "type": "string",
                        "description": "Type of relationship"
                    },
                    "confidence": {
                        "type": "integer",
                        "description": "Confidence score 0-100"
                    }
                },
                "required": ["source", "target", "relationship", "confidence"]
            }
        }
    },
    "required": ["relationships"]
}


# =====================================
# PROMPT MAPPING
# =====================================

ENTITY_TYPE_PROMPTS = {
    "actor": EXTRACT_ACTORS_PROMPT,
    "policy": EXTRACT_POLICIES_PROMPT,
    "outcome": EXTRACT_OUTCOMES_PROMPT,
    "risk": EXTRACT_RISKS_PROMPT,
}

"""Common entity alias dictionary for pre-loaded deduplication.

This dictionary contains known aliases for common entities. Using this
dictionary eliminates the need for LLM calls on obvious duplicates.

Format:
    canonical_label: [alias1, alias2, alias3, ...]

When an entity matches any alias in a group, it will be merged to the
canonical label (key).
"""

from typing import Optional

# Actor aliases - Countries and Organizations
ACTOR_ALIASES = {
    # United States
    "United States": [
        "US",
        "USA",
        "U.S.",
        "U.S.A.",
        "America",
        "United States of America",
        "the United States",
        "the US",
        "the USA",
    ],

    # United Kingdom
    "United Kingdom": [
        "UK",
        "U.K.",
        "Britain",
        "Great Britain",
        "the United Kingdom",
        "the UK",
        "Great Britain and Northern Ireland",
    ],

    # European Union
    "European Union": [
        "EU",
        "E.U.",
        "the European Union",
        "the EU",
    ],

    # United Nations
    "United Nations": [
        "UN",
        "U.N.",
        "the United Nations",
        "the UN",
    ],

    # Israel
    "Israel": [
        "State of Israel",
        "the State of Israel",
    ],

    # Russia
    "Russia": [
        "Russian Federation",
        "the Russian Federation",
    ],

    # China
    "China": [
        "People's Republic of China",
        "PRC",
        "the PRC",
    ],

    # US Congress
    "US Congress": [
        "United States Congress",
        "Congress",
        "the Congress",
        "U.S. Congress",
    ],

    # US Senate
    "US Senate": [
        "United States Senate",
        "the Senate",
        "U.S. Senate",
    ],

    # US House of Representatives
    "US House of Representatives": [
        "House of Representatives",
        "the House",
        "US House",
    ],

    # White House
    "White House": [
        "the White House",
        "Executive Office of the President",
    ],

    # NATO
    "NATO": [
        "North Atlantic Treaty Organization",
        "the North Atlantic Treaty Organization",
    ],

    # World Bank
    "World Bank": [
        "the World Bank",
        "International Bank for Reconstruction and Development",
    ],

    # International Monetary Fund
    "International Monetary Fund": [
        "IMF",
        "the IMF",
    ],

    # World Health Organization
    "World Health Organization": [
        "WHO",
        "the WHO",
    ],

    # European Central Bank
    "European Central Bank": [
        "ECB",
        "the ECB",
    ],

    # Federal Reserve
    "Federal Reserve": [
        "Fed",
        "the Fed",
        "Federal Reserve System",
    ],

    # Supreme Court (US)
    "Supreme Court": [
        "US Supreme Court",
        "United States Supreme Court",
        "the Supreme Court",
    ],

    # Department of Defense (US)
    "Department of Defense": [
        "DoD",
        "DOD",
        "the Pentagon",
    ],
}

# Policy aliases
POLICY_ALIASES = {
    # Sanctions
    "Sanctions": [
        "Economic Sanctions",
        "Trade Sanctions",
        "the Sanctions",
    ],

    # Trade Policy
    "Trade Policy": [
        "Trade Agreement",
        "Trade Deal",
        "Free Trade Agreement",
    ],

    # Foreign Aid
    "Foreign Aid": [
        "International Aid",
        "Development Assistance",
        "Foreign Assistance",
    ],

    # Military Aid
    "Military Aid": [
        "Security Assistance",
        "Defense Assistance",
        "Military Assistance",
    ],
}

# Combined dictionary for easy lookup
ALL_ALIASES = {
    **ACTOR_ALIASES,
    **POLICY_ALIASES,
}


def get_canonical_label(label: str, entity_type: str = "actor") -> Optional[str]:
    """Get the canonical label for a given entity label.

    Args:
        label: The entity label to check
        entity_type: The entity type (actor, policy, outcome, risk)

    Returns:
        The canonical label if found, None otherwise
    """
    normalized = label.lower().strip()

    # Check in combined dictionary first
    for canonical, aliases in ALL_ALIASES.items():
        if normalized == canonical.lower():
            return canonical
        for alias in aliases:
            if normalized == alias.lower():
                return canonical

    # Type-specific lookup if needed
    type_specific = ACTOR_ALIASES if entity_type == "actor" else POLICY_ALIASES
    for canonical, aliases in type_specific.items():
        if normalized == canonical.lower():
            return canonical
        for alias in aliases:
            if normalized == alias.lower():
                return canonical

    return None


def is_alias_match(label1: str, label2: str, entity_type: str = "actor") -> bool:
    """Check if two labels are aliases of the same canonical entity.

    Args:
        label1: First label
        label2: Second label
        entity_type: The entity type

    Returns:
        True if labels are aliases of the same entity
    """
    canonical1 = get_canonical_label(label1, entity_type)
    canonical2 = get_canonical_label(label2, entity_type)

    if canonical1 and canonical2:
        return canonical1 == canonical2

    # Also check if either directly matches the other's canonical form
    if canonical1:
        return label2.lower().strip() == canonical1.lower()
    if canonical2:
        return label1.lower().strip() == canonical2.lower()

    return False

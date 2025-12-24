# Agent System Architecture

## 1. System Overview

The Deep Policy Analyst uses a sophisticated multi-agent system to perform deep research, extraction, and synthesis. The system is designed for high reliability, provenance tracking, and fault tolerance.

### Core Features

| Feature | Priority | Notes |
| :--- | :--- | :--- |
| **Multi-agent orchestration** | P0 | Coordinator pattern with specialized workers. |
| **Source retrieval agents** | P0 | Search, fetch, and normalize data from external sources. |
| **APOR extraction agents** | P0 | NER for **A**ctor, **P**olicy, **O**utcome, **R**isk entities. |
| **Relationship extraction agents** | P0 | Detection of relationships between APOR entities. |
| **Synthesis agents** | P0 | APOR-structured summarization and reporting. |
| **Checkpoint persistence** | P0 | State saving to resume from failure. |
| **Provenance tracking** | P0 | Every output node/edge is linked to its source. |
| **Confidence scoring** | P0 | Based on source quality and claim support. |

---

## 2. Agent Architecture

Agents are specialized workers with defined inputs, outputs, and failure handling mechanisms.

### 2.1 Agent Properties

Every agent in the system must adhere to these properties:

*   **Task ID**: Unique identifier for tracking and state resumption.
*   **Input Schema**: Strictly typed parameters the agent accepts.
*   **Output Schema**: Structured results (often including APOR entities).
*   **Timeout**: Hard limits on execution time before escalation/cancellation.
*   **Retry Policy**: Defined attempts, backoff strategy, and fallback behavior.
*   **Cost Cap**: Maximum token/compute budget per execution.
*   **Model Routing**: Configuration for which LLM(s) the agent uses (e.g., GPT-4 for logic, Haiku for volume).
*   **Checkpoint Frequency**: Interval definition for persisting intermediate state.

### 2.2 Agent Types

1.  **Retriever Agent**
    *   Executes search queries across configured sources (Web, APIs, Internal DB).
    *   Normalizes results to a common schema.
    *   Handles pagination, rate limiting, and cleaning.

2.  **APOR Extractor Agent**
    *   Processes raw documents to identify entities.
    *   **A**ctor: Who is involved?
    *   **P**olicy: What is the action/rule?
    *   **O**utcome: What is the result?
    *   **R**isk: What could go wrong?
    *   Classifies entities with confidence scores.

3.  **Relationship Agent**
    *   Detects semantic connections between APOR entities.
    *   Outputs typed edges (e.g., `Actor` *implements* `Policy`).

4.  **Synthesizer Agent**
    *   Multi-pass summarization.
    *   Produces report sections organized by APOR structure.

5.  **Hypothesis Agent**
    *   Generates competing interpretations of Actor-Policy-Outcome chains.
    *   Scores interpretations against evidence.

6.  **Visualizer Agent**
    *   Transforms the APOR graph into renderable payloads (JSON for D3/Vis.js).

---

## 3. APOR Knowledge Graph

Central to the platform is the typed knowledge graph.

*   **Nodes**: All entities typed as **Actor** (Blue), **Policy** (Purple), **Outcome** (Green), or **Risk** (Red).
    *   Attributes: Canonical name, aliases, confidence, provenance.
*   **Edges**: Relationships from a defined vocabulary.
    *   Examples: `implements`, `causes`, `mitigates`, `opposes`, `supports`.
    *   Attributes: Confidence, temporal bounds, provenance.
*   **Queries**: Support for complex traversals.
    *   *Example*: "Find all Policies implemented by Actor X that caused Outcomes affecting Actor Y."

---

## 4. Resilience Patterns

The system is built to fail gracefully and recover automatically.

*   **Checkpointing**: Agents write progress to durable storage (Redis/Postgres) at configurable intervals. On failure, the system resumes from the last checkpoint rather than restarting.
*   **Graceful Degradation**: If deep analysis times out or fails, returns a partial APOR graph with a completion percentage and an option to continue later.
*   **Model Fallback**: If the primary LLM is unavailable or rate-limited, automatically routes to a secondary provider or uses cached responses.
*   **Idempotent Operations**: All tasks are keyed by stable IDs. Retrying a task does not duplicate side effects.
*   **Circuit Breakers**: Automatic isolation of failing services/APIs to prevent cascading failures.

---

## 5. Observability & Checkpoint System

### 5.1 Progress Visibility
Users must never face a black box.

*   **Stage Indicators**: Visual tracking: Retrieval → APOR Extraction → Synthesis → Output.
*   **APOR Counters**: Real-time counts of extracted entities.
*   **Agent Status**: Status text per agent (Pending, Running, Complete, Failed, Retrying).
*   **Real-Time Logs**: Streaming logs of agent actions ("Searching...", "Found 5 documents...").

### 5.2 Checkpoint Architecture
Checkpoints are structured snapshots:

*   **Job-level**: Overall progress, configuration.
*   **Stage-level**: Inputs consumed, outputs produced.
*   **Agent-level**: Internal state, documents processed.
*   **Graph checkpoint**: Snapshot of the current Knowledge Graph.

**Storage**: Object storage (or JSONB in DB) with Retantion policy (default 30 days).

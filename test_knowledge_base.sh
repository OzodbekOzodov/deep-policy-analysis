#!/bin/bash
# Knowledge Base Pipeline Sanity Check Test Script
# Tests the complete flow: upload -> process -> search -> query expansion

set -e

API_URL="http://localhost:8000"
LLM_GATEWAY_URL="http://localhost:8001"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Knowledge Base Pipeline Sanity Check       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# TEST 1: Health Checks
# ============================================================================
echo -e "${BLUE}[TEST 1] Health Checks${NC}"

if curl -s "$API_URL/health" | grep -q "ok"; then
  echo -e "  ${GREEN}✓${NC} Backend is healthy"
else
  echo -e "  ${RED}✗${NC} Backend is not healthy"
  exit 1
fi

if curl -s "$LLM_GATEWAY_URL/health" | grep -q "ok"; then
  echo -e "  ${GREEN}✓${NC} LLM Gateway is healthy"
else
  echo -e "  ${RED}✗${NC} LLM Gateway is not healthy"
  exit 1
fi

echo ""

# ============================================================================
# TEST 2: Get Initial Stats
# ============================================================================
echo -e "${BLUE}[TEST 2] Initial Knowledge Base Stats${NC}"
INITIAL_STATS=$(curl -s "$API_URL/api/knowledge/stats")
echo "$INITIAL_STATS" | python3 -m json.tool
INITIAL_PENDING=$(echo "$INITIAL_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['documents']['pending'])" 2>/dev/null || echo "0")
INITIAL_INDEXED=$(echo "$INITIAL_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['documents']['indexed'])" 2>/dev/null || echo "0")
echo ""

# ============================================================================
# TEST 3: Upload Text Document
# ============================================================================
echo -e "${BLUE}[TEST 3] Upload Text Document${NC}"

TEST_TEXT="Artificial Intelligence Policy Framework

The rapid advancement of artificial intelligence (AI) technologies presents both opportunities and challenges for policymakers. This framework outlines key considerations:

1. Governance: Establish clear regulatory oversight for AI development and deployment.
2. Safety: Ensure AI systems are safe, secure, and aligned with human values.
3. Innovation: Promote research and development while managing risks.
4. International Cooperation: Coordinate with allies to establish global standards.

Risks identified include:
- Algorithmic bias and discrimination
- Privacy and surveillance concerns
- Economic displacement due to automation
- Dual-use military applications

Recommended actions:
- Create an AI Safety Board with regulatory authority
- Establish liability frameworks for AI-caused harms
- Invest in AI safety research
- Develop international treaties on AI weapons systems
"

UPLOAD_RESPONSE=$(curl -s -X POST "$API_URL/api/knowledge/documents" \
  -F "text=$TEST_TEXT" \
  -F "title=Test AI Policy Document" \
  -F "content_type=text/plain" \
  -F "source_type=test")

echo "$UPLOAD_RESPONSE" | python3 -m json.tool

DOCUMENT_ID=$(echo "$UPLOAD_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['document_id'])" 2>/dev/null)

if [ -n "$DOCUMENT_ID" ]; then
  echo -e "  ${GREEN}✓${NC} Text document uploaded with ID: $DOCUMENT_ID"
else
  echo -e "  ${RED}✗${NC} Failed to upload text document"
  exit 1
fi
echo ""

# ============================================================================
# TEST 4: Verify Document is Pending
# ============================================================================
echo -e "${BLUE}[TEST 4] Verify Document Status is 'pending'${NC}"

STATS_AFTER_UPLOAD=$(curl -s "$API_URL/api/knowledge/stats")
PENDING_AFTER_UPLOAD=$(echo "$STATS_AFTER_UPLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin)['documents']['pending'])" 2>/dev/null || echo "0")

if [ "$PENDING_AFTER_UPLOAD" -gt "$INITIAL_PENDING" ]; then
  echo -e "  ${GREEN}✓${NC} Pending count increased (was $INITIAL_PENDING, now $PENDING_AFTER_UPLOAD)"
else
  echo -e "  ${YELLOW}⚠${NC} Pending count did not increase as expected"
fi
echo ""

# ============================================================================
# TEST 5: Get Document Details
# ============================================================================
echo -e "${BLUE}[TEST 5] Get Document Details${NC}"

DOC_DETAILS=$(curl -s "$API_URL/api/knowledge/documents?status=pending&limit=10")
echo "$DOC_DETAILS" | python3 -m json.tool
echo ""

# ============================================================================
# TEST 6: Process Pending Documents
# ============================================================================
echo -e "${BLUE}[TEST 6] Process Pending Documents${NC}"

PROCESS_RESPONSE=$(curl -s -X POST "$API_URL/api/knowledge/process?limit=10")
echo "$PROCESS_RESPONSE" | python3 -m json.tool

PROCESSED=$(echo "$PROCESS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['processed'])" 2>/dev/null || echo "0")
SUCCESSFUL=$(echo "$PROCESS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['successful'])" 2>/dev/null || echo "0")
FAILED=$(echo "$PROCESS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['failed'])" 2>/dev/null || echo "0")

echo ""
if [ "$SUCCESSFUL" -gt 0 ]; then
  echo -e "  ${GREEN}✓${NC} Processed: $SUCCESSFUL successful, $FAILED failed"
else
  echo -e "  ${RED}✗${NC} No documents were processed successfully"
fi
echo ""

# ============================================================================
# TEST 7: Verify Document is Indexed
# ============================================================================
echo -e "${BLUE}[TEST 7] Verify Document is Now 'indexed'${NC}"

sleep 2  # Give a moment for the database to settle

FINAL_STATS=$(curl -s "$API_URL/api/knowledge/stats")
echo "$FINAL_STATS" | python3 -m json.tool

FINAL_INDEXED=$(echo "$FINAL_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['documents']['indexed'])" 2>/dev/null || echo "0")
FINAL_PENDING=$(echo "$FINAL_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['documents']['pending'])" 2>/dev/null || echo "0")

echo ""
if [ "$FINAL_INDEXED" -gt "$INITIAL_INDEXED" ]; then
  echo -e "  ${GREEN}✓${NC} Indexed count increased (was $INITIAL_INDEXED, now $FINAL_INDEXED)"
else
  echo -e "  ${YELLOW}⚠${NC} Indexed count did not increase"
fi
echo ""

# ============================================================================
# TEST 8: Vector Search
# ============================================================================
echo -e "${BLUE}[TEST 8] Vector Search Test${NC}"

SEARCH_QUERY="artificial intelligence safety governance"
SEARCH_RESPONSE=$(curl -s -X POST "$API_URL/api/knowledge/search" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$SEARCH_QUERY\", \"limit\": 5}")

echo "Search query: '$SEARCH_QUERY'"
echo "$SEARCH_RESPONSE" | python3 -m json.tool

RESULT_COUNT=$(echo "$SEARCH_RESPONSE" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data)) if isinstance(data,list) else 0" 2>/dev/null || echo "0")

echo ""
if [ "$RESULT_COUNT" -gt 0 ]; then
  echo -e "  ${GREEN}✓${NC} Found $RESULT_COUNT relevant chunks"
else
  echo -e "  ${YELLOW}⚠${NC} No search results found"
fi
echo ""

# ============================================================================
# TEST 9: Query Expansion
# ============================================================================
echo -e "${BLUE}[TEST 9] Query Expansion Test${NC}"

EXPAND_QUERY="AI policy risks"
EXPAND_RESPONSE=$(curl -s -X POST "$API_URL/api/knowledge/expand" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$EXPAND_QUERY\", \"num_expansions\": 10}")

echo "Original query: '$EXPAND_QUERY'"
echo "$EXPAND_RESPONSE" | python3 -m json.tool

EXPANSION_COUNT=$(echo "$EXPAND_RESPONSE" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data.get('expansions',[])))" 2>/dev/null || echo "0")

echo ""
if [ "$EXPANSION_COUNT" -gt 0 ]; then
  echo -e "  ${GREEN}✓${NC} Generated $EXPANSION_COUNT query expansions"
else
  echo -e "  ${RED}✗${NC} Query expansion failed"
fi
echo ""

# ============================================================================
# TEST 10: Direct Database Verification
# ============================================================================
echo -e "${BLUE}[TEST 10] Direct Database Verification${NC}"

echo "Checking document in database..."
if [ -n "$DOCUMENT_ID" ]; then
  psql dap -c "SELECT id, title, processing_status, LENGTH(raw_content) as content_size, created_at, processed_at FROM documents WHERE id = '$DOCUMENT_ID';" 2>/dev/null || echo "  (psql not available - skipping direct DB check)"
fi

echo ""
echo "Checking chunks in database..."
psql dap -c "SELECT COUNT(*) as chunk_count, COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embedded_count FROM chunks WHERE document_id = '$DOCUMENT_ID';" 2>/dev/null || echo "  (psql not available - skipping direct DB check)"
echo ""

# ============================================================================
# TEST 11: List Indexed Documents
# ============================================================================
echo -e "${BLUE}[TEST 11] List Indexed Documents${NC}"

INDEXED_DOCS=$(curl -s "$API_URL/api/knowledge/documents?status=indexed&limit=5")
echo "$INDEXED_DOCS" | python3 -m json.tool
echo ""

# ============================================================================
# TEST 12: Test Empty Search (Edge Case)
# ============================================================================
echo -e "${BLUE}[TEST 12] Edge Case Tests${NC}"

echo "Testing empty query handling..."
EMPTY_SEARCH=$(curl -s -X POST "$API_URL/api/knowledge/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "", "limit": 5}' 2>&1)

if echo "$EMPTY_SEARCH" | grep -q "422\|validation"; then
  echo -e "  ${GREEN}✓${NC} Empty query properly rejected"
else
  echo -e "  ${YELLOW}⚠${NC} Empty query response: $EMPTY_SEARCH"
fi
echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Test Summary                               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "Final Knowledge Base Stats:"
curl -s "$API_URL/api/knowledge/stats" | python3 -m json.tool
echo ""
echo -e "${GREEN}✓ Sanity check complete!${NC}"

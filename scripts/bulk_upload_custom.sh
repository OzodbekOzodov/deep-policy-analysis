#!/bin/bash
# Bulk Upload Script for Knowledge Base
# Usage: ./bulk_upload.sh /path/to/documents [batch_size]

set -e

# Configuration
DOCS_DIR="${1:-.}"
BATCH_SIZE="${2:-50}"
API_URL="http://localhost:8000"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Knowledge Base Bulk Upload Script   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if directory exists
if [ ! -d "$DOCS_DIR" ]; then
  echo -e "${RED}✗ Directory not found: $DOCS_DIR${NC}"
  exit 1
fi

# Check if backend is running
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
  echo -e "${RED}✗ Backend not reachable at $API_URL${NC}"
  echo "  Start backend with: cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000"
  exit 1
fi

echo -e "${GREEN}✓ Backend is running${NC}"
echo ""

# Count files
PDF_COUNT=$(find "$DOCS_DIR" -type f -name "*.pdf" | wc -l | tr -d ' ')
TXT_COUNT=$(find "$DOCS_DIR" -type f -name "*.txt" | wc -l | tr -d ' ')
HTML_COUNT=$(find "$DOCS_DIR" -type f \( -name "*.html" -o -name "*.htm" \) | wc -l | tr -d ' ')
TOTAL=$((PDF_COUNT + TXT_COUNT + HTML_COUNT))

echo -e "${BLUE}Found files:${NC}"
echo "  PDFs:  $PDF_COUNT"
echo "  Text:  $TXT_COUNT"
echo "  HTML:  $HTML_COUNT"
echo "  Total: $TOTAL"
echo ""

if [ "$TOTAL" -eq 0 ]; then
  echo -e "${YELLOW}No supported files found in $DOCS_DIR${NC}"
  exit 0
fi

# Confirm
read -p "Upload $TOTAL documents to knowledge base? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

echo ""
echo -e "${BLUE}Step 1: Uploading documents...${NC}"

UPLOADED=0
FAILED=0

# Upload PDFs
while IFS= read -r file; do
  [ -f "$file" ] || continue

  title=$(basename "$file" .pdf)

  if curl -s -X POST "$API_URL/api/knowledge/documents" \
    -F "file=@$file" \
    -F "title=$title" \
    -F "source_type=upload" > /dev/null 2>&1; then
    UPLOADED=$((UPLOADED + 1))
    echo -e "  ${GREEN}✓${NC} Queued: $title"
  else
    FAILED=$((FAILED + 1))
    echo -e "  ${RED}✗${NC} Failed: $title"
  fi
done < <(find "$DOCS_DIR" -type f -name "*.pdf")

# Upload text files
while IFS= read -r file; do
  [ -f "$file" ] || continue

  title=$(basename "$file" .txt)

  if curl -s -X POST "$API_URL/api/knowledge/documents" \
    -F "file=@$file" \
    -F "title=$title" \
    -F "source_type=upload" > /dev/null 2>&1; then
    UPLOADED=$((UPLOADED + 1))
    echo -e "  ${GREEN}✓${NC} Queued: $title"
  else
    FAILED=$((FAILED + 1))
    echo -e "  ${RED}✗${NC} Failed: $title"
  fi
done < <(find "$DOCS_DIR" -type f -name "*.txt")

# Upload HTML files
while IFS= read -r file; do
  [ -f "$file" ] || continue

  title=$(basename "$file" .html)
  title=${title%.htm}

  if curl -s -X POST "$API_URL/api/knowledge/documents" \
    -F "file=@$file" \
    -F "title=$title" \
    -F "source_type=upload" > /dev/null 2>&1; then
    UPLOADED=$((UPLOADED + 1))
    echo -e "  ${GREEN}✓${NC} Queued: $title"
  else
    FAILED=$((FAILED + 1))
    echo -e "  ${RED}✗${NC} Failed: $title"
  fi
done < <(find "$DOCS_DIR" -type f \( -name "*.html" -o -name "*.htm" \))

echo ""
echo -e "${GREEN}Upload complete: $UPLOADED succeeded, $FAILED failed${NC}"

if [ "$UPLOADED" -eq 0 ]; then
  echo -e "${YELLOW}No documents uploaded. Exiting.${NC}"
  exit 0
fi

echo ""
echo -e "${BLUE}Step 2: Current stats${NC}"
curl -s "$API_URL/api/knowledge/stats" | python3 -m json.tool 2>/dev/null || echo "  (stats unavailable)"

echo ""
read -p "Process pending documents now? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
  echo ""
  echo -e "${YELLOW}Documents queued but not processed.${NC}"
  echo "Process later with:"
  echo "  curl -X POST $API_URL/api/knowledge/process"
  exit 0
fi

echo ""
echo -e "${BLUE}Step 3: Processing documents in batches of $BATCH_SIZE...${NC}"

TOTAL_PROCESSED=0
BATCH_NUM=1

while true; do
  echo -e "  ${BLUE}Batch $BATCH_NUM...${NC}"

  RESULT=$(curl -s -X POST "$API_URL/api/knowledge/process?limit=$BATCH_SIZE")

  PROCESSED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['processed'])" 2>/dev/null || echo "0")
  SUCCESSFUL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['successful'])" 2>/dev/null || echo "0")
  BATCH_FAILED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['failed'])" 2>/dev/null || echo "0")

  if [ "$PROCESSED" -eq "0" ]; then
    break
  fi

  TOTAL_PROCESSED=$((TOTAL_PROCESSED + PROCESSED))
  echo -e "    ${GREEN}✓${NC} Processed: $SUCCESSFUL, Failed: $BATCH_FAILED"

  BATCH_NUM=$((BATCH_NUM + 1))
  sleep 1
done

echo ""
echo -e "${GREEN}Processing complete! Total processed: $TOTAL_PROCESSED${NC}"

echo ""
echo -e "${BLUE}Final stats:${NC}"
curl -s "$API_URL/api/knowledge/stats" | python3 -m json.tool 2>/dev/null || echo "  (stats unavailable)"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            All Done! ✓                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

#!/bin/bash
# Upload Knowledge Base Documents
# Scans ./knowledge_base folder and uploads all documents
# Usage: ./scripts/upload_knowledge_base.sh [auto]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
KB_DIR="$PROJECT_ROOT/knowledge_base"
API_URL="http://localhost:8000"
AUTO_PROCESS="${1:-}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Knowledge Base Upload Script              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Check if knowledge_base folder exists
if [ ! -d "$KB_DIR" ]; then
  echo -e "${RED}✗ Knowledge base folder not found: $KB_DIR${NC}"
  echo "  Expected: $PROJECT_ROOT/knowledge_base/"
  exit 1
fi

# Check if backend is running
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
  echo -e "${RED}✗ Backend not reachable at $API_URL${NC}"
  echo "  Start backend with:"
  echo "    cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000"
  echo ""
  echo "  Or use: ./dev.sh"
  exit 1
fi

echo -e "${GREEN}✓ Backend is running${NC}"
echo -e "${BLUE}✓ Knowledge base folder: $KB_DIR${NC}"
echo ""

# Count files (recursive search)
PDF_COUNT=$(find "$KB_DIR" -type f -name "*.pdf" ! -path "*/.*" | wc -l | tr -d ' ')
TXT_COUNT=$(find "$KB_DIR" -type f -name "*.txt" ! -path "*/.*" | wc -l | tr -d ' ')
HTML_COUNT=$(find "$KB_DIR" -type f \( -name "*.html" -o -name "*.htm" \) ! -path "*/.*" | wc -l | tr -d ' ')
TOTAL=$((PDF_COUNT + TXT_COUNT + HTML_COUNT))

echo -e "${BLUE}Found documents in knowledge_base/:${NC}"
echo "  PDFs:  $PDF_COUNT"
echo "  Text:  $TXT_COUNT"
echo "  HTML:  $HTML_COUNT"
echo "  ─────────────"
echo "  Total: $TOTAL"
echo ""

if [ "$TOTAL" -eq 0 ]; then
  echo -e "${YELLOW}No documents found in knowledge_base/${NC}"
  echo ""
  echo "Add documents:"
  echo "  cp /path/to/your/docs/*.pdf $KB_DIR/"
  echo ""
  echo "Then run this script again."
  exit 0
fi

# Auto-confirm if 'auto' argument provided
if [ "$AUTO_PROCESS" != "auto" ]; then
  read -p "Upload $TOTAL documents to knowledge base? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
  fi
fi

echo ""
echo -e "${BLUE}Uploading documents...${NC}"

UPLOADED=0
FAILED=0
SKIPPED=0

# Upload PDFs
while IFS= read -r file; do
  [ -f "$file" ] || continue

  # Skip hidden files and README
  basename_file=$(basename "$file")
  if [[ "$basename_file" == .* ]] || [[ "$basename_file" == "README.md" ]]; then
    continue
  fi

  title=$(basename "$file" .pdf)
  rel_path="${file#$KB_DIR/}"

  if curl -s -X POST "$API_URL/api/knowledge/documents" \
    -F "file=@$file" \
    -F "title=$title" \
    -F "source_type=knowledge_base" > /dev/null 2>&1; then
    UPLOADED=$((UPLOADED + 1))
    echo -e "  ${GREEN}✓${NC} $rel_path"
  else
    FAILED=$((FAILED + 1))
    echo -e "  ${RED}✗${NC} $rel_path"
  fi
done < <(find "$KB_DIR" -type f -name "*.pdf" ! -path "*/.*")

# Upload text files
while IFS= read -r file; do
  [ -f "$file" ] || continue

  basename_file=$(basename "$file")
  if [[ "$basename_file" == .* ]] || [[ "$basename_file" == "README.md" ]]; then
    continue
  fi

  title=$(basename "$file" .txt)
  rel_path="${file#$KB_DIR/}"

  if curl -s -X POST "$API_URL/api/knowledge/documents" \
    -F "file=@$file" \
    -F "title=$title" \
    -F "source_type=knowledge_base" > /dev/null 2>&1; then
    UPLOADED=$((UPLOADED + 1))
    echo -e "  ${GREEN}✓${NC} $rel_path"
  else
    FAILED=$((FAILED + 1))
    echo -e "  ${RED}✗${NC} $rel_path"
  fi
done < <(find "$KB_DIR" -type f -name "*.txt" ! -path "*/.*")

# Upload HTML files
while IFS= read -r file; do
  [ -f "$file" ] || continue

  basename_file=$(basename "$file")
  if [[ "$basename_file" == .* ]]; then
    continue
  fi

  title=$(basename "$file" .html)
  title=${title%.htm}
  rel_path="${file#$KB_DIR/}"

  if curl -s -X POST "$API_URL/api/knowledge/documents" \
    -F "file=@$file" \
    -F "title=$title" \
    -F "source_type=knowledge_base" > /dev/null 2>&1; then
    UPLOADED=$((UPLOADED + 1))
    echo -e "  ${GREEN}✓${NC} $rel_path"
  else
    FAILED=$((FAILED + 1))
    echo -e "  ${RED}✗${NC} $rel_path"
  fi
done < <(find "$KB_DIR" -type f \( -name "*.html" -o -name "*.htm" \) ! -path "*/.*")

echo ""
if [ "$FAILED" -gt 0 ]; then
  echo -e "${YELLOW}Upload complete: $UPLOADED succeeded, $FAILED failed${NC}"
else
  echo -e "${GREEN}Upload complete: $UPLOADED documents queued${NC}"
fi

if [ "$UPLOADED" -eq 0 ]; then
  echo -e "${YELLOW}No documents uploaded.${NC}"
  exit 0
fi

echo ""
echo -e "${BLUE}Current knowledge base stats:${NC}"
curl -s "$API_URL/api/knowledge/stats" | python3 -m json.tool 2>/dev/null || echo "  (stats unavailable)"

# Auto-process if 'auto' argument provided
if [ "$AUTO_PROCESS" = "auto" ]; then
  echo ""
  echo -e "${BLUE}Auto-processing enabled...${NC}"
  PROCESS_RESPONSE=$(curl -s -X POST "$API_URL/api/knowledge/process")
  echo "$PROCESS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$PROCESS_RESPONSE"

  echo ""
  echo -e "${BLUE}Final stats:${NC}"
  curl -s "$API_URL/api/knowledge/stats" | python3 -m json.tool 2>/dev/null

  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║         All Done! ✓                          ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
  exit 0
fi

echo ""
read -p "Process pending documents now? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
  echo ""
  echo -e "${YELLOW}Documents queued but not processed.${NC}"
  echo "Process later with:"
  echo "  curl -X POST $API_URL/api/knowledge/process"
  echo ""
  echo "Or run this script with 'auto' flag:"
  echo "  ./scripts/upload_knowledge_base.sh auto"
  exit 0
fi

echo ""
echo -e "${BLUE}Processing all pending documents...${NC}"

TOTAL_PROCESSED=0
BATCH_NUM=1
BATCH_SIZE=50

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
echo -e "${GREEN}Processing complete! Total: $TOTAL_PROCESSED documents${NC}"

echo ""
echo -e "${BLUE}Final knowledge base stats:${NC}"
curl -s "$API_URL/api/knowledge/stats" | python3 -m json.tool 2>/dev/null || echo "  (stats unavailable)"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         All Done! ✓                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "Your documents are now searchable in the knowledge base!"

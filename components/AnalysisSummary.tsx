import React, { useState } from 'react';
import { AnalysisSummaryResponse, CitationItem } from '../types';
import TypewriterText from './TypewriterText';
import { FileText, X } from 'lucide-react';

interface AnalysisSummaryProps {
  summary: AnalysisSummaryResponse | null;
  isLoading?: boolean;
}

const AnalysisSummary: React.FC<AnalysisSummaryProps> = ({ summary, isLoading = false }) => {
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  // Parse summary to wrap citations in clickable spans
  const renderSummaryWithCitations = (text: string) => {
    const citationRegex = /\[(\d+)\]/g;
    const parts: Array<{ text: string; isCitation: boolean; citationNum?: number }> = [];
    let lastIndex = 0;
    let match;

    while ((match = citationRegex.exec(text)) !== null) {
      // Add text before this citation
      if (match.index > lastIndex) {
        parts.push({ text: text.slice(lastIndex, match.index), isCitation: false });
      }

      // Add the citation marker
      parts.push({
        text: `[${match[1]}]`,
        isCitation: true,
        citationNum: parseInt(match[1], 10)
      });

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push({ text: text.slice(lastIndex), isCitation: false });
    }

    return parts;
  };

  const handleCitationClick = (citationNum: number) => {
    const citation = summary?.citations.find(c => c.id === citationNum);
    if (citation) {
      setSelectedCitation(citation);
    }
  };

  if (isLoading) {
    return (
      <div className="mb-6">
        <h3 className="text-xs font-mono text-nexus-400 uppercase tracking-widest mb-3 flex items-center gap-2">
          <span className="w-2 h-2 bg-nexus-400 rounded-full animate-pulse"></span>
          Analysis Summary
        </h3>
        <div className="p-5 rounded-xl bg-nexus-900/60 border border-nexus-800 shadow-inner">
          <div className="flex items-center justify-center py-8">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-nexus-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-nexus-400 font-mono">Generating analysis...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!summary) {
    return null;
  }

  const summaryParts = renderSummaryWithCitations(summary.summary);

  return (
    <div className="mb-6">
      <h3 className="text-xs font-mono text-nexus-400 uppercase tracking-widest mb-3 flex items-center gap-2">
        <span className="w-2 h-2 bg-nexus-400 rounded-full animate-pulse"></span>
        Analysis Summary
      </h3>
      <div className="p-5 rounded-xl bg-nexus-900/60 border border-nexus-800 shadow-inner font-mono text-sm leading-relaxed text-slate-300">
        <div className="space-y-2">
          {summaryParts.map((part, idx) =>
            part.isCitation ? (
              <button
                key={`citation-${idx}-${part.citationNum}`}
                onClick={() => handleCitationClick(part.citationNum!)}
                className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-nexus-500/10 border border-nexus-500/30 text-nexus-400 hover:bg-nexus-500/20 hover:border-nexus-500/50 transition-all cursor-pointer hover:shadow-[0_0_8px_rgba(59,130,246,0.3)]"
                title="View source"
              >
                [{part.citationNum}]
              </button>
            ) : (
              <span key={`text-${idx}`} className="inline">
                {part.text}
              </span>
            )
          )}
        </div>

        {summary.citations.length > 0 && (
          <div className="mt-4 pt-4 border-t border-nexus-800">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-3 h-3 text-slate-500" />
              <span className="text-[10px] text-slate-500 font-mono uppercase">
                {summary.citations.length} Source{summary.citations.length > 1 ? 's' : ''} Cited
              </span>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {summary.citations.map((citation) => (
                <button
                  key={citation.id}
                  onClick={() => setSelectedCitation(citation)}
                  className="text-left p-2 rounded bg-nexus-950/50 border border-nexus-800 hover:border-nexus-600 hover:bg-nexus-900/80 transition-all group"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-[10px] font-mono text-nexus-500 mt-0.5">[{citation.id}]</span>
                    <span className="text-xs text-slate-400 group-hover:text-slate-300 transition-colors line-clamp-1">
                      {citation.document_title || 'Unknown Source'}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Citation Popover */}
      {selectedCitation && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedCitation(null)}
        >
          <div
            className="bg-nexus-950 border border-nexus-700 rounded-lg shadow-2xl max-w-lg w-full max-h-[80vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-nexus-800">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-nexus-400" />
                <span className="text-sm font-mono font-bold text-slate-200">
                  CITATION [{selectedCitation.id}]
                </span>
              </div>
              <button
                onClick={() => setSelectedCitation(null)}
                className="p-1 hover:bg-nexus-800 rounded transition-colors text-slate-500 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content */}
            <div className="p-4 overflow-y-auto max-h-[60vh] custom-scrollbar">
              <div className="mb-4">
                <span className="text-[10px] text-slate-500 font-mono uppercase">Source</span>
                <p className="text-sm text-slate-200 font-mono mt-1">
                  {selectedCitation.document_title || 'Unknown Document'}
                </p>
              </div>

              <div className="mb-4">
                <span className="text-[10px] text-slate-500 font-mono uppercase">Quote</span>
                <p className="text-sm text-slate-300 mt-1 leading-relaxed border-l-2 border-nexus-700 pl-3 bg-nexus-900/30 py-2 rounded-r">
                  "{selectedCitation.text}"
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-[10px] text-slate-500 font-mono uppercase">Relationship</span>
                  <p className="text-xs text-nexus-400 font-mono mt-1">
                    {selectedCitation.relationship}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 font-mono uppercase">Confidence</span>
                  <p className="text-xs text-nexus-400 font-mono mt-1">
                    {selectedCitation.confidence}%
                  </p>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-3 border-t border-nexus-800 bg-nexus-900/30">
              <span className="text-[9px] text-slate-600 font-mono">
                Chunk ID: {selectedCitation.chunk_id.slice(0, 8)}...
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisSummary;

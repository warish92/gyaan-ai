"use client";

import React, { useState } from "react";
import { Check, Copy, Sigma } from "lucide-react";

export interface FormattedMessageProps {
  content: string;
  className?: string;
}

/**
 * Replace common LaTeX math commands and symbols with readable Unicode representations.
 */
function formatMathSymbols(math: string): string {
  return math
    // Chemical and mathematical arrows
    .replace(/\\rightleftharpoons/g, "⇌")
    .replace(/\\leftrightarrow/g, "↔")
    .replace(/\\rightarrow|\\to/g, "→")
    .replace(/\\leftarrow/g, "←")
    .replace(/\\Rightarrow/g, "⇒")
    .replace(/\\Leftarrow/g, "⇐")
    // Mathematical operators & relations
    .replace(/\\times/g, "×")
    .replace(/\\cdot/g, "·")
    .replace(/\\div/g, "÷")
    .replace(/\\pm/g, "±")
    .replace(/\\mp/g, "∓")
    .replace(/\\approx/g, "≈")
    .replace(/\\neq/g, "≠")
    .replace(/\\leq|\\le/g, "≤")
    .replace(/\\geq|\\ge/g, "≥")
    .replace(/\\equiv/g, "≡")
    .replace(/\\propto/g, "∝")
    .replace(/\\infty/g, "∞")
    .replace(/\\partial/g, "∂")
    .replace(/\\nabla/g, "∇")
    .replace(/\\sum/g, "∑")
    .replace(/\\prod/g, "∏")
    .replace(/\\sqrt\{([^}]+)\}/g, "√($1)")
    .replace(/\\sqrt/g, "√")
    // Greek letters used in Class 10 Science & Math
    .replace(/\\alpha/g, "α")
    .replace(/\\beta/g, "β")
    .replace(/\\gamma/g, "γ")
    .replace(/\\delta/g, "δ")
    .replace(/\\Delta/g, "Δ")
    .replace(/\\epsilon/g, "ε")
    .replace(/\\theta/g, "θ")
    .replace(/\\lambda/g, "λ")
    .replace(/\\mu/g, "μ")
    .replace(/\\pi/g, "π")
    .replace(/\\rho/g, "ρ")
    .replace(/\\sigma/g, "σ")
    .replace(/\\Sigma/g, "Σ")
    .replace(/\\phi/g, "φ")
    .replace(/\\omega/g, "ω")
    .replace(/\\Omega/g, "Ω")
    // Fractions: \frac{a}{b} -> (a / b)
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "($1 / $2)")
    // Text labels in math
    .replace(/\\text\{([^}]+)\}/g, "$1")
    .replace(/\\mathrm\{([^}]+)\}/g, "$1")
    .replace(/\\mathbf\{([^}]+)\}/g, "$1")
    // Common CBSE Class 10 Superscripts & Subscripts
    .replace(/\^2\b|\^\{2\}/g, "²")
    .replace(/\^3\b|\^\{3\}/g, "³")
    .replace(/\^0\b|\^\{0\}/g, "⁰")
    .replace(/\^1\b|\^\{1\}/g, "¹")
    .replace(/\^n\b|\^\{n\}/g, "ⁿ")
    .replace(/\^\+\b|\^\{\+\}/g, "⁺")
    .replace(/\^-\b|\^\{-\}/g, "⁻")
    .replace(/_2\b|_\{2\}/g, "₂")
    .replace(/_3\b|_\{3\}/g, "₃")
    .replace(/_4\b|_\{4\}/g, "₄")
    .replace(/_1\b|_\{1\}/g, "₁")
    .replace(/_0\b|_\{0\}/g, "₀")
    .replace(/_i\b|_\{i\}/g, "ᵢ")
    .trim();
}

function isTableRow(line: string): boolean {
  const t = line.trim();
  return t.startsWith("|") && t.endsWith("|") && t.length > 2;
}

function isTableSeparator(line: string): boolean {
  const t = line.trim();
  return isTableRow(t) && /^\|[\s-:]+(\|[\s-:]+)+\|$/.test(t);
}

export const FormattedMessage: React.FC<FormattedMessageProps> = ({ content, className = "" }) => {
  const [copiedCodeIdx, setCopiedCodeIdx] = useState<number | null>(null);

  const handleCopyCode = async (code: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCodeIdx(idx);
      setTimeout(() => setCopiedCodeIdx(null), 2000);
    } catch {
      // Fallback
    }
  };

  // Parse inline text: code, bold, italics, inline math
  const renderInline = (text: string) => {
    const parts: React.ReactNode[] = [];
    const remaining = text;
    let keyIdx = 0;

    // Tokens:
    // 1) Inline code: `code`
    // 2) Bold: **bold**
    // 3) Italic: *italic*
    // 4) LaTeX inline: $math$ (excluding literal \$) or \(math\)
    const tokenRegex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\$[^$\n]+\$|\\\([^)]+\\\))/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = tokenRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        parts.push(remaining.substring(lastIndex, match.index));
      }
      const token = match[0];

      if (token.startsWith("`") && token.endsWith("`")) {
        parts.push(
          <code
            key={keyIdx++}
            className="px-1.5 py-0.5 rounded bg-slate-100 font-mono text-xs text-blue-700 font-medium border border-slate-200"
          >
            {token.slice(1, -1)}
          </code>
        );
      } else if (token.startsWith("**") && token.endsWith("**")) {
        parts.push(
          <strong key={keyIdx++} className="font-semibold text-[#172033]">
            {token.slice(2, -2)}
          </strong>
        );
      } else if (token.startsWith("*") && token.endsWith("*")) {
        parts.push(
          <em key={keyIdx++} className="italic text-slate-700">
            {token.slice(1, -1)}
          </em>
        );
      } else if (
        (token.startsWith("$") && token.endsWith("$") && token.length > 2) ||
        (token.startsWith("\\(") && token.endsWith("\\)"))
      ) {
        const rawMath = token.startsWith("$") ? token.slice(1, -1) : token.slice(2, -2);
        const formatted = formatMathSymbols(rawMath);
        parts.push(
          <span
            key={keyIdx++}
            className="inline-flex items-center px-1.5 py-0.5 rounded bg-blue-50/80 text-blue-900 font-serif text-[13px] border border-blue-200/60 mx-0.5 shadow-2xs select-all"
            title={rawMath}
          >
            {formatted}
          </span>
        );
      }
      lastIndex = tokenRegex.lastIndex;
    }

    if (lastIndex < remaining.length) {
      parts.push(remaining.substring(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];

  let currentBullets: string[] = [];
  let currentNumbered: string[] = [];
  let currentTable: string[] = [];
  let currentBlockquote: string[] = [];

  let inCodeBlock = false;
  let codeBlockLines: string[] = [];
  let codeLanguage = "";

  const flushBullets = (key: number) => {
    if (currentBullets.length > 0) {
      blocks.push(
        <ul key={`ul-${key}`} className="my-2 space-y-1 list-disc list-outside ml-5 text-sm text-slate-800">
          {currentBullets.map((item, idx) => (
            <li key={idx} className="leading-relaxed">
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      currentBullets = [];
    }
  };

  const flushNumbered = (key: number) => {
    if (currentNumbered.length > 0) {
      blocks.push(
        <ol key={`ol-${key}`} className="my-2 space-y-1 list-decimal list-outside ml-5 text-sm text-slate-800">
          {currentNumbered.map((item, idx) => (
            <li key={idx} className="leading-relaxed">
              {renderInline(item)}
            </li>
          ))}
        </ol>
      );
      currentNumbered = [];
    }
  };

  const flushBlockquote = (key: number) => {
    if (currentBlockquote.length > 0) {
      blocks.push(
        <blockquote
          key={`bq-${key}`}
          className="my-3 border-l-4 border-blue-500 bg-blue-50/40 px-3.5 py-2 rounded-r-lg text-sm text-slate-800 italic space-y-1"
        >
          {currentBlockquote.map((line, idx) => (
            <p key={idx} className="leading-relaxed">
              {renderInline(line)}
            </p>
          ))}
        </blockquote>
      );
      currentBlockquote = [];
    }
  };

  const flushTable = (key: number) => {
    if (currentTable.length >= 2) {
      const sepIdx = currentTable.findIndex(isTableSeparator);
      if (sepIdx >= 1) {
        const headerRows = currentTable.slice(0, sepIdx);
        const bodyRows = currentTable.slice(sepIdx + 1);

        const parseCells = (row: string) =>
          row
            .trim()
            .slice(1, -1)
            .split("|")
            .map((c) => c.trim());

        blocks.push(
          <div key={`table-${key}`} className="my-3 overflow-x-auto rounded-xl border border-slate-200/90 shadow-2xs bg-white">
            <table className="w-full text-xs text-left border-collapse">
              <thead className="bg-slate-100/90 text-slate-700 font-bold border-b border-slate-200">
                {headerRows.map((hRow, hIdx) => (
                  <tr key={`h-${hIdx}`}>
                    {parseCells(hRow).map((cell, cIdx) => (
                      <th key={`th-${cIdx}`} className="px-3.5 py-2.5 whitespace-nowrap">
                        {renderInline(cell)}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-800">
                {bodyRows.map((bRow, bIdx) => (
                  <tr key={`b-${bIdx}`} className="even:bg-slate-50/50 hover:bg-blue-50/30 transition-colors">
                    {parseCells(bRow).map((cell, cIdx) => (
                      <td key={`td-${cIdx}`} className="px-3.5 py-2 leading-relaxed">
                        {renderInline(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      } else {
        // Fallback: render lines as regular paragraphs
        currentTable.forEach((line, lIdx) => {
          blocks.push(
            <p key={`table-fallback-${key}-${lIdx}`} className="my-1 text-sm text-slate-800">
              {renderInline(line)}
            </p>
          );
        });
      }
      currentTable = [];
    } else if (currentTable.length === 1) {
      blocks.push(
        <p key={`table-single-${key}`} className="my-1 text-sm text-slate-800">
          {renderInline(currentTable[0])}
        </p>
      );
      currentTable = [];
    }
  };

  const flushAllLists = (key: number) => {
    flushBullets(key);
    flushNumbered(key);
    flushBlockquote(key);
    flushTable(key);
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Code block fence
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        // End of code block
        const codeText = codeBlockLines.join("\n");
        const blockIdx = i;
        blocks.push(
          <div
            key={`code-${i}`}
            className="my-3 rounded-xl bg-slate-900 text-slate-100 shadow-inner border border-slate-800 overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-1.5 bg-slate-950/80 border-b border-slate-800 text-[11px] text-slate-400 font-sans">
              <span className="uppercase tracking-wider font-semibold">
                {codeLanguage || "code"}
              </span>
              <button
                onClick={() => handleCopyCode(codeText, blockIdx)}
                className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 transition-colors"
                title="Copy code"
              >
                {copiedCodeIdx === blockIdx ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span className="text-[10px] text-emerald-400">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span className="text-[10px]">Copy</span>
                  </>
                )}
              </button>
            </div>
            <pre className="p-4 font-mono text-xs overflow-x-auto leading-relaxed">{codeText}</pre>
          </div>
        );
        inCodeBlock = false;
        codeBlockLines = [];
        codeLanguage = "";
      } else {
        flushAllLists(i);
        inCodeBlock = true;
        codeLanguage = trimmed.replace("```", "").trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockLines.push(rawLine);
      continue;
    }

    // 2. Table row detection
    if (isTableRow(trimmed)) {
      flushBullets(i);
      flushNumbered(i);
      flushBlockquote(i);
      currentTable.push(trimmed);
      continue;
    } else if (currentTable.length > 0) {
      flushTable(i);
    }

    // 3. Blockquote detection
    if (trimmed.startsWith("> ")) {
      flushBullets(i);
      flushNumbered(i);
      currentBlockquote.push(trimmed.substring(2));
      continue;
    } else if (currentBlockquote.length > 0) {
      flushBlockquote(i);
    }

    // 4. Horizontal rule
    if (trimmed === "---" || trimmed === "***" || trimmed === "___") {
      flushAllLists(i);
      blocks.push(<hr key={`hr-${i}`} className="my-4 border-slate-200" />);
      continue;
    }

    // 5. Markdown headers
    if (trimmed.startsWith("### ")) {
      flushAllLists(i);
      blocks.push(
        <h4 key={`h4-${i}`} className="text-base font-bold text-[#172033] mt-4 mb-2 pb-1 border-b border-slate-100">
          {renderInline(trimmed.substring(4))}
        </h4>
      );
      continue;
    }
    if (trimmed.startsWith("## ")) {
      flushAllLists(i);
      blocks.push(
        <h3 key={`h3-${i}`} className="text-lg font-bold text-[#172033] mt-5 mb-2 pb-1 border-b border-slate-100">
          {renderInline(trimmed.substring(3))}
        </h3>
      );
      continue;
    }
    if (trimmed.startsWith("# ")) {
      flushAllLists(i);
      blocks.push(
        <h2 key={`h2-${i}`} className="text-xl font-extrabold text-[#172033] mt-5 mb-2 pb-1 border-b border-slate-200">
          {renderInline(trimmed.substring(2))}
        </h2>
      );
      continue;
    }

    // 6. LaTeX equation block: \[ ... \] or $$ ... $$
    const isLatexBlock =
      (trimmed.startsWith("\\[") && trimmed.endsWith("\\]")) ||
      (trimmed.startsWith("$$") && trimmed.endsWith("$$") && trimmed.length > 4);
    if (isLatexBlock) {
      flushAllLists(i);
      const rawMath = trimmed.startsWith("\\[")
        ? trimmed.substring(2, trimmed.length - 2).trim()
        : trimmed.substring(2, trimmed.length - 2).trim();
      const formattedMath = formatMathSymbols(rawMath);
      blocks.push(
        <div
          key={`math-${i}`}
          className="my-3 py-3 px-5 rounded-xl bg-gradient-to-r from-blue-50/70 via-slate-50 to-indigo-50/50 border border-blue-200 font-serif text-sm sm:text-base text-slate-900 text-center overflow-x-auto shadow-2xs select-all flex items-center justify-center gap-2"
        >
          <Sigma className="w-4 h-4 text-blue-600 shrink-0 select-none" />
          <span className="font-medium tracking-wide">{formattedMath}</span>
        </div>
      );
      continue;
    }

    // 7. Bullet points
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      flushNumbered(i);
      currentBullets.push(trimmed.substring(2));
      continue;
    }

    // 8. Numbered list items
    const numberedMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
    if (numberedMatch) {
      flushBullets(i);
      currentNumbered.push(numberedMatch[2]);
      continue;
    }

    // 9. Empty line / paragraph break
    if (trimmed === "") {
      flushAllLists(i);
      continue;
    }

    // 10. Regular paragraph
    flushAllLists(i);
    blocks.push(
      <p key={`p-${i}`} className="my-2 leading-relaxed text-sm text-[#172033]">
        {renderInline(rawLine)}
      </p>
    );
  }

  flushAllLists(lines.length);

  return <div className={`space-y-1 ${className}`}>{blocks}</div>;
};

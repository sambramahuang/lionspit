/* ---------------------------------------------------------------------
   Draft text -> editable HTML

   The model writes plain text with **bold** spans, [[n]] citation
   markers, [[GAP: ...]] / [[UNCITED]] flags, and standalone "---"
   dividers. This turns that into an HTML string safe to drop into a
   contentEditable surface via dangerouslySetInnerHTML: citation/gap/
   uncited tokens render as contenteditable="false" atoms so a lawyer
   editing the surrounding prose can't accidentally type through one and
   silently corrupt the citation trail.
------------------------------------------------------------------------ */

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inlineMarkdownToHtml(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

export function renderDraftHtml(text) {
  const regex = /\[\[(GAP:[^\]]*|UNCITED|\d+)\]\]|^[ \t]*-{3,}[ \t]*$/gm;
  let html = "";
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      html += inlineMarkdownToHtml(text.slice(lastIndex, match.index));
    }
    const token = match[1];
    if (token === undefined) {
      html += '<hr class="draft-divider" contenteditable="false" />';
    } else if (token === "UNCITED") {
      html +=
        '<span class="uncited-badge" contenteditable="false" title="Not cited to any source -- review before use">⚠ uncited</span>';
    } else if (token.startsWith("GAP:")) {
      const gapText = token.slice(4).trim();
      html += `<span class="gap-badge" contenteditable="false" data-gap="${escapeHtml(
        gapText
      )}">gap: ${escapeHtml(gapText)}</span>`;
    } else {
      html += `<button type="button" class="cite-badge" contenteditable="false" data-marker="${token}">${token}</button>`;
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) html += inlineMarkdownToHtml(text.slice(lastIndex));
  return html;
}

/* ---------------------------------------------------------------------
   Live-edited DOM -> structured paragraphs

   Reads the *current* (possibly hand-edited) contentEditable DOM back
   into an array of paragraphs, each an array of runs {text, bold, kind}.
   kind is undefined for ordinary prose, or "citation" | "gap" |
   "uncited" | "divider" -- used by every export format below so an
   edited draft exports exactly what's on screen, not the original
   AI output.
------------------------------------------------------------------------ */

function gapTextOf(el) {
  return el.dataset?.gap ?? el.textContent.replace(/^gap:\s*/i, "");
}

export function domToParagraphs(root) {
  const paragraphs = [];
  let current = [];
  const flush = () => {
    if (current.length) {
      paragraphs.push(current);
      current = [];
    }
  };
  const pushRun = (run) => {
    if (run.text !== "") current.push(run);
  };

  const walk = (node, bold) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const segments = node.nodeValue.split("\n");
      segments.forEach((seg, i) => {
        if (i > 0) flush();
        if (seg) pushRun({ text: seg, bold });
      });
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const tag = node.tagName;
    if (tag === "BR") {
      flush();
      return;
    }
    if (tag === "HR") {
      flush();
      paragraphs.push([{ text: "", bold: false, kind: "divider" }]);
      return;
    }
    const cls = node.classList;
    if (cls?.contains("cite-badge")) {
      pushRun({ text: `[${node.dataset.marker}]`, bold: false, kind: "citation" });
      return;
    }
    if (cls?.contains("gap-badge")) {
      pushRun({ text: `[GAP: ${gapTextOf(node)}]`, bold: false, kind: "gap" });
      return;
    }
    if (cls?.contains("uncited-badge")) {
      pushRun({ text: "[UNCITED]", bold: false, kind: "uncited" });
      return;
    }
    const nowBold = bold || tag === "STRONG" || tag === "B";
    const isBlock = tag === "DIV" || tag === "P" || tag === "LI";
    for (const child of node.childNodes) walk(child, nowBold);
    if (isBlock) flush();
  };

  for (const child of root.childNodes) walk(child, false);
  flush();
  return paragraphs.length ? paragraphs : [[{ text: "", bold: false }]];
}

function paragraphsToPlainText(paragraphs) {
  return paragraphs
    .map((runs) => {
      if (runs.length === 1 && runs[0].kind === "divider") return "-".repeat(60);
      return runs.map((r) => r.text).join("");
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function buildAppendixParagraphs(draft) {
  const paras = [];
  if (draft.citations?.length) {
    paras.push([{ text: "SOURCES", bold: true }]);
    draft.citations.forEach((c) => {
      paras.push([
        { text: `[${c.marker}] `, bold: true, kind: "citation" },
        { text: c.filename, bold: false },
      ]);
      if (c.excerpt) paras.push([{ text: `"...${c.excerpt}"`, bold: false }]);
    });
  }
  if (draft.gaps?.length) {
    paras.push([{ text: "GAPS FLAGGED, NOT INVENTED", bold: true }]);
    draft.gaps.forEach((g) => paras.push([{ text: `- ${g}`, bold: false, kind: "gap" }]));
  }
  if (draft.flagged_uncited?.length) {
    paras.push([{ text: "UNCITED CLAUSES -- REVIEW BEFORE RELYING ON THESE", bold: true }]);
    draft.flagged_uncited.forEach((c) => paras.push([{ text: `- ${c}`, bold: false, kind: "uncited" }]));
  }
  return paras;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/* ---------------------------------------------------------------------
   .txt
------------------------------------------------------------------------ */

export function downloadDraftTxt(rootEl, draft, filenameBase = "draft") {
  const body = paragraphsToPlainText(domToParagraphs(rootEl));
  const appendix = paragraphsToPlainText(buildAppendixParagraphs(draft));
  const text = appendix ? `${body}\n\n${appendix}` : body;
  triggerDownload(new Blob([text], { type: "text/plain;charset=utf-8" }), `${filenameBase}.txt`);
}

/* ---------------------------------------------------------------------
   .docx
------------------------------------------------------------------------ */

const DOCX_COLOR = { citation: "1B2430", gap: "A8453A", uncited: "A8453A" };

// docx/jspdf (and jspdf's optional html2canvas/dompurify plugins) are
// sizeable and only needed by someone who actually clicks a download
// button, so they're dynamically imported inside each export function
// rather than at module scope -- most sessions (search/browse/draft
// without exporting) never pull either library in at all.
export async function downloadDraftDocx(rootEl, draft, filenameBase = "draft") {
  const { Document, Packer, Paragraph, TextRun, HeadingLevel, BorderStyle } = await import("docx");

  const runsToTextRuns = (runs) =>
    runs.map(
      (r) =>
        new TextRun({
          text: r.text,
          bold: !!r.bold || r.kind === "uncited",
          color: DOCX_COLOR[r.kind],
        })
    );

  const paragraphsToDocx = (paragraphs) =>
    paragraphs.map((runs) => {
      if (runs.length === 1 && runs[0].kind === "divider") {
        return new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "D8D3C4" } },
          spacing: { after: 200 },
        });
      }
      return new Paragraph({ children: runsToTextRuns(runs), spacing: { after: 160 } });
    });

  const bodyParagraphs = paragraphsToDocx(domToParagraphs(rootEl));
  const appendixSource = buildAppendixParagraphs(draft);

  const appendixParagraphs = appendixSource.map((runs) => {
    const isHeading = runs.length === 1 && runs[0].bold && !runs[0].kind;
    return isHeading
      ? new Paragraph({ text: runs[0].text, heading: HeadingLevel.HEADING_3, spacing: { before: 260, after: 100 } })
      : new Paragraph({ children: runsToTextRuns(runs), spacing: { after: 100 } });
  });

  const doc = new Document({
    sections: [{ children: [...bodyParagraphs, ...appendixParagraphs] }],
  });
  const blob = await Packer.toBlob(doc);
  triggerDownload(blob, `${filenameBase}.docx`);
}

/* ---------------------------------------------------------------------
   .pdf
------------------------------------------------------------------------ */

const PDF_INK = [27, 36, 48];
const PDF_RED = [168, 69, 58];
const PDF_MUTED = [92, 101, 112];
const PDF_RULE = [216, 211, 196];

function layoutParagraphs(doc, paragraphs, opts) {
  const { marginLeft, marginRight, marginTop, marginBottom, lineHeight, pageWidth, pageHeight, fontSize } = opts;
  const maxX = pageWidth - marginRight;
  let x = marginLeft;
  let y = opts.startY;

  const newLine = () => {
    x = marginLeft;
    y += lineHeight;
    if (y > pageHeight - marginBottom) {
      doc.addPage();
      y = marginTop;
    }
  };

  const setRunStyle = (run) => {
    doc.setFont("helvetica", run.bold || run.kind === "uncited" ? "bold" : "normal");
    doc.setFontSize(fontSize);
    if (run.kind === "citation") doc.setTextColor(...PDF_INK);
    else if (run.kind === "gap" || run.kind === "uncited") doc.setTextColor(...PDF_RED);
    else doc.setTextColor(...PDF_INK);
  };

  paragraphs.forEach((runs) => {
    if (runs.length === 1 && runs[0].kind === "divider") {
      newLine();
      doc.setDrawColor(...PDF_RULE);
      doc.line(marginLeft, y - lineHeight / 3, maxX, y - lineHeight / 3);
      newLine();
      return;
    }
    runs.forEach((run) => {
      setRunStyle(run);
      const words = run.text.split(" ");
      words.forEach((word, wi) => {
        const piece = wi === 0 ? word : " " + word;
        const w = doc.getTextWidth(piece);
        if (x + w > maxX) {
          newLine();
          const trimmed = piece.replace(/^ /, "");
          doc.text(trimmed, x, y);
          x += doc.getTextWidth(trimmed);
        } else {
          doc.text(piece, x, y);
          x += w;
        }
      });
    });
    newLine();
    y += lineHeight * 0.35;
    x = marginLeft;
  });

  return y;
}

export async function downloadDraftPdf(rootEl, draft, filenameBase = "draft") {
  const { jsPDF } = await import("jspdf");
  const paragraphs = domToParagraphs(rootEl);
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const marginLeft = 56;
  const marginRight = 56;
  const marginTop = 56;
  const marginBottom = 56;

  let y = marginTop;
  doc.setFont("times", "bold");
  doc.setFontSize(16);
  doc.setTextColor(...PDF_INK);
  doc.text("Draft", marginLeft, y);
  y += 20;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(...PDF_MUTED);
  doc.text("Generated by Kitsu -- every clause footnoted back to its source", marginLeft, y);
  y += 22;

  y = layoutParagraphs(doc, paragraphs, {
    marginLeft,
    marginRight,
    marginTop,
    marginBottom,
    lineHeight: 16,
    pageWidth,
    pageHeight,
    fontSize: 11,
    startY: y,
  });

  const appendixParas = buildAppendixParagraphs(draft);
  if (appendixParas.length) {
    y += 8;
    if (y > pageHeight - marginBottom - 40) {
      doc.addPage();
      y = marginTop;
    }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(13);
    doc.setTextColor(...PDF_INK);
    doc.text("Sources & Notes", marginLeft, y);
    y += 18;
    layoutParagraphs(doc, appendixParas, {
      marginLeft,
      marginRight,
      marginTop,
      marginBottom,
      lineHeight: 15,
      pageWidth,
      pageHeight,
      fontSize: 10,
      startY: y,
    });
  }

  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8.5);
    doc.setTextColor(150, 150, 150);
    doc.text(`${i} / ${pageCount}`, pageWidth - marginRight, pageHeight - 28, { align: "right" });
  }

  doc.save(`${filenameBase}.pdf`);
}

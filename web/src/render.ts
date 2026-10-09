import { Marked } from "marked";
import type { Artifact, Citation } from "./api";

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const isHttp = (href: string) => /^https?:\/\//i.test(href);

/**
 * Chat answers are model output shown in the main page (not in the sandbox), so raw HTML is
 * escaped, only http(s) links survive, and images are dropped (architecture §7).
 */
const chatMarked = new Marked({
  gfm: true,
  renderer: {
    html: ({ text }) => escapeHtml(text),
    image: ({ text }) => escapeHtml(text),
    link({ href, tokens }) {
      const label = this.parser.parseInline(tokens);
      return isHttp(href) ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
    },
  },
});

export function renderAnswer(markdown: string, citations: Citation[]): string {
  const html = chatMarked.parse(markdown, { async: false });
  return html.replace(/\[(\d+)\]/g, (match, n: string) => {
    const c = citations[Number(n) - 1];
    if (!c) return match;
    const label = escapeHtml(`Source ${n}: ${c.guest ?? "Unknown guest"}, ${c.title}`);
    return c.url
      ? `<a class="cite" href="${escapeHtml(c.url)}" target="_blank" rel="noopener noreferrer" aria-label="${label}">[${n}]</a>`
      : `<span class="cite" aria-label="${label}">[${n}]</span>`;
  });
}

const CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:";

const ARTIFACT_STYLE = `
  :root { color-scheme: light dark; }
  body { margin: 0 auto; padding: 24px 28px 48px; max-width: 72ch; font: 17px/1.65 Georgia, "Times New Roman", serif;
         color: #1f2328; background: #fff; }
  h1, h2, h3 { line-height: 1.25; }
  pre, code { font-family: ui-monospace, Consolas, monospace; font-size: 0.9em; }
  table { border-collapse: collapse; } th, td { border: 1px solid #d0d7de; padding: 4px 8px; }
  a { color: inherit; }
  @media (prefers-color-scheme: dark) { body { color: #e6edf3; background: #0d1117; } th, td { border-color: #30363d; } }
`;

/** Full document for <iframe sandbox="" srcdoc>: no scripts, no network, no forms (architecture §7). */
export function artifactDocument(artifact: Artifact): string {
  const body = artifact.type === "markdown" ? (new Marked().parse(artifact.content, { async: false }) as string) : artifact.content;
  return `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${CSP}">
<style>${ARTIFACT_STYLE}</style></head><body>${body}</body></html>`;
}

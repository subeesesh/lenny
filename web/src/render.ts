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

/** One-pager design applied to the fixed structure the server produces: header, one section per heading, sources footer. */
const ONE_PAGER_STYLE = `
  :root { color-scheme: light dark; --bg: #f5f7fb; --card: #ffffff; --text: #1f2328; --muted: #59636e;
          --accent: #2554c7; --accent-2: #6d3fc7; --soft: #eef3ff; --border: #e1e6ef; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #0d1117; --card: #161b22; --text: #e6edf3; --muted: #9da7b3; --accent: #7aa7ff; --accent-2: #b08cff;
            --soft: #142238; --border: #30363d; }
  }
  * { box-sizing: border-box; }
  body { margin: 0 auto; padding: 28px 22px 40px; max-width: 980px; background: var(--bg); color: var(--text);
         font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  body:has(> header) { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; align-content: start; }
  header, footer, section:last-of-type { grid-column: 1 / -1; }
  header { padding: 28px 28px 24px; border-radius: 16px; color: #fff;
           background: linear-gradient(135deg, var(--accent), var(--accent-2)); }
  header h1 { margin: 0 0 8px; font-size: clamp(1.6rem, 3.2vw, 2.25rem); line-height: 1.2; }
  header p { margin: 0; font-size: 1.1rem; opacity: 0.93; }
  section { padding: 20px 22px; border: 1px solid var(--border); border-radius: 14px; background: var(--card); }
  section h2 { margin: 0 0 10px; font-size: 1.12rem; line-height: 1.3; color: var(--accent); }
  section p { margin: 0 0 10px; }
  section > :last-child { margin-bottom: 0; }
  ul, ol { margin: 0 0 10px; padding-left: 1.25em; }
  li { margin: 5px 0; }
  li::marker { color: var(--accent); }
  blockquote { margin: 12px 0 0; padding: 12px 16px; border-left: 4px solid var(--accent); border-radius: 8px;
               background: var(--soft); font-style: italic; }
  section:last-of-type { background: var(--soft); border-color: var(--accent); }
  section:last-of-type h2 { color: var(--text); }
  table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
  footer { padding: 4px 6px; font-size: 0.85rem; color: var(--muted); }
  footer h2 { margin: 6px 0; font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; }
  footer ol { margin: 0; }
  a { color: inherit; }
`;

/** Full document for <iframe sandbox="" srcdoc>: no scripts, no network, no forms (architecture §7). */
export function artifactDocument(artifact: Artifact): string {
  const markdown = artifact.type === "markdown";
  const body = markdown ? (new Marked().parse(artifact.content, { async: false }) as string) : artifact.content;
  return `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${CSP}">
<style>${markdown ? ARTIFACT_STYLE : ONE_PAGER_STYLE}</style></head><body>${body}</body></html>`;
}

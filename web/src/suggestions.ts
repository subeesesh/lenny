/**
 * Example questions for the empty state. Every one was checked against the real transcripts
 * (retrieval above the threshold and a sourced answer from the local model) on 2026-10-10.
 * Avoid the words "doc", "essay", "html" or "markdown": the router would treat them as document requests.
 */
const POOL = [
  "How does Shreyas Doshi describe the LNO framework?",
  "What does April Dunford say is the first step in positioning?",
  "How does Teresa Torres recommend running continuous discovery interviews?",
  "What advice does Julie Zhuo give to first-time managers?",
  "How does Brian Chesky think about leaders being in the details?",
  "What does Elena Verna say about product-led growth for B2B?",
  "How does Casey Winters explain growth loops versus funnels?",
  "How does Rahul Vohra measure product-market fit at Superhuman?",
  "How should early-stage startups think about pricing?",
  "What does Madhavan Ramanujam say about pricing conversations with customers?",
  "How do guests recommend prioritizing a product roadmap?",
  "What do guests say about writing a good product spec or PRD?",
  "How should a new PM spend their first 90 days?",
  "What do Lenny's guests say about hiring great product managers?",
  "How do guests think about building a growth team?",
  "What is the jobs-to-be-done framework according to Bob Moesta?",
  "How does Marty Cagan describe empowered product teams?",
  "What does Wes Kao recommend for managing up?",
  "How do guests think about user onboarding and activation?",
  "What does Annie Duke say about quitting and decision-making?",
  "How does Dylan Field describe Figma's early days?",
  "What do guests say about network effects?",
  "How does Gokul Rajaram think about hiring and team building?",
  "What is a north star metric and how do guests choose one?",
  "How do guests recommend writing a product strategy?",
  "What do guests say about giving and receiving feedback?",
];

const KEY = "lga.seenSuggestions";

function readSeen(): string[] {
  try {
    const seen = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(seen) ? seen : [];
  } catch {
    return [];
  }
}

function shuffle<T>(items: T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Picks `count` questions not shown before in this browser; starts over once the whole pool has been shown. */
export function pickSuggestions(count = 3): string[] {
  let seen = readSeen().filter((q) => POOL.includes(q));
  let fresh = POOL.filter((q) => !seen.includes(q));
  if (fresh.length < count) {
    const lastShown = seen.slice(-count);
    seen = [];
    fresh = POOL.filter((q) => !lastShown.includes(q));
  }
  const picked = shuffle(fresh).slice(0, count);
  try {
    localStorage.setItem(KEY, JSON.stringify([...seen, ...picked]));
  } catch {
    /* private mode: suggestions are still random, just not tracked */
  }
  return picked;
}

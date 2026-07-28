// One-shot handoff of a scraped research answer into the AI Studio prompt
// composer, so scraper results are actually usable by the content flow
// instead of being a dead-end research silo.
const KEY = "creditflow_scraper_prompt_seed";

export function setScraperPromptSeed(seed: string) {
  sessionStorage.setItem(KEY, seed);
}

export function consumeScraperPromptSeed(): string | null {
  const value = sessionStorage.getItem(KEY);
  if (value) sessionStorage.removeItem(KEY);
  return value;
}

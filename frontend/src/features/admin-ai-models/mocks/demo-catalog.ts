/*
 * The curated OpenRouter models Admin › AI-модели manages without a backend, with demo prices and a
 * simulated weekday load. Live names, context lengths and prices replace these when the server has
 * an OpenRouter key; see ai-models.ts.
 */

export type CatalogEntry = {
  id: string;
  openrouter_id: string;
  name: string;
  provider: string;
  context_length: number;
  price_input_per_m: number;
  price_output_per_m: number;
  /** Simulated weekday load: requests a day and average tokens per request. */
  usage: { requests: number; tokens_in: number; tokens_out: number };
};

export const DEFAULT_MODEL_ID = "claude-sonnet-4-5";

export const CATALOG: CatalogEntry[] = [
  {
    id: "claude-sonnet-4-5",
    openrouter_id: "anthropic/claude-sonnet-4.5",
    name: "Claude Sonnet 4.5",
    provider: "Anthropic",
    context_length: 1_000_000,
    price_input_per_m: 3,
    price_output_per_m: 15,
    usage: { requests: 1850, tokens_in: 5200, tokens_out: 720 },
  },
  {
    id: "claude-haiku-4-5",
    openrouter_id: "anthropic/claude-haiku-4.5",
    name: "Claude Haiku 4.5",
    provider: "Anthropic",
    context_length: 200_000,
    price_input_per_m: 1,
    price_output_per_m: 5,
    usage: { requests: 3400, tokens_in: 2600, tokens_out: 380 },
  },
  {
    id: "gpt-5",
    openrouter_id: "openai/gpt-5",
    name: "GPT-5",
    provider: "OpenAI",
    context_length: 400_000,
    price_input_per_m: 1.25,
    price_output_per_m: 10,
    usage: { requests: 920, tokens_in: 4800, tokens_out: 900 },
  },
  {
    id: "gpt-5-mini",
    openrouter_id: "openai/gpt-5-mini",
    name: "GPT-5 Mini",
    provider: "OpenAI",
    context_length: 400_000,
    price_input_per_m: 0.25,
    price_output_per_m: 2,
    usage: { requests: 2100, tokens_in: 2200, tokens_out: 420 },
  },
  {
    id: "gemini-2-5-pro",
    openrouter_id: "google/gemini-2.5-pro",
    name: "Gemini 2.5 Pro",
    provider: "Google",
    context_length: 1_048_576,
    price_input_per_m: 1.25,
    price_output_per_m: 10,
    usage: { requests: 640, tokens_in: 9800, tokens_out: 850 },
  },
  {
    id: "gemini-2-5-flash",
    openrouter_id: "google/gemini-2.5-flash",
    name: "Gemini 2.5 Flash",
    provider: "Google",
    context_length: 1_048_576,
    price_input_per_m: 0.3,
    price_output_per_m: 2.5,
    usage: { requests: 2900, tokens_in: 3100, tokens_out: 360 },
  },
  {
    id: "deepseek-chat-v3-1",
    openrouter_id: "deepseek/deepseek-chat-v3.1",
    name: "DeepSeek V3.1",
    provider: "DeepSeek",
    context_length: 163_840,
    price_input_per_m: 0.27,
    price_output_per_m: 1.1,
    usage: { requests: 410, tokens_in: 3600, tokens_out: 540 },
  },
  {
    id: "llama-4-maverick",
    openrouter_id: "meta-llama/llama-4-maverick",
    name: "Llama 4 Maverick",
    provider: "Meta",
    context_length: 1_048_576,
    price_input_per_m: 0.15,
    price_output_per_m: 0.6,
    usage: { requests: 0, tokens_in: 0, tokens_out: 0 },
  },
  {
    id: "mistral-medium-3-1",
    openrouter_id: "mistralai/mistral-medium-3.1",
    name: "Mistral Medium 3.1",
    provider: "Mistral",
    context_length: 131_072,
    price_input_per_m: 0.4,
    price_output_per_m: 2,
    usage: { requests: 0, tokens_in: 0, tokens_out: 0 },
  },
];

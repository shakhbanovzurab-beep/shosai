import type { CardBrand } from "@/lib/card-brand";

import type { McpTransport } from "./mcp-contract";

/*
 * Names shown as they are in every interface language: card networks and MCP transports are proper names,
 * not words to translate. What has no name of its own (an unknown card) is worded by the UI.
 */

/** Card networks, written next to their logos. */
export const CARD_BRAND_NAMES: Record<Exclude<CardBrand, "unknown">, string> = {
  visa: "Visa",
  mastercard: "Mastercard",
  amex: "American Express",
  discover: "Discover",
  jcb: "JCB",
  diners: "Diners Club",
  unionpay: "UnionPay",
  mir: "Mir",
};

/** MCP transports as the protocol names them, in full for the picker and short for a server's badge. */
export const MCP_TRANSPORT_NAMES: Record<McpTransport, { full: string; short: string }> = {
  streamable_http: { full: "Streamable HTTP", short: "HTTP" },
  sse: { full: "SSE", short: "SSE" },
};

/**
 * Payment card networks as the payment provider reports them. Shared by the user's own billing
 * (Settings) and the admin finance screens, which describe the same cards.
 */
export type CardBrand = "visa" | "mastercard" | "amex" | "discover" | "jcb" | "diners" | "unionpay" | "mir" | "unknown";

// Allowed values of the layout preferences; the controls take their labels from the `layoutControls` messages.

export const SIDEBAR_VARIANT_VALUES = ["sidebar", "inset", "floating"] as const;
export type SidebarVariant = (typeof SIDEBAR_VARIANT_VALUES)[number];

export const SIDEBAR_COLLAPSIBLE_VALUES = ["icon", "offcanvas"] as const;
export type SidebarCollapsible = (typeof SIDEBAR_COLLAPSIBLE_VALUES)[number];

export const CONTENT_LAYOUT_VALUES = ["centered", "full-width"] as const;

export const NAVBAR_STYLE_VALUES = ["sticky", "scroll"] as const;

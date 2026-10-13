# Shosai brand mark

The mark is two sliding shoji panels: the front panel has slid over the back one, and the door is open. It reads as a person entering their own study (書斎, *shosai*) — a quiet room where Shosai remembers, connects and helps act. See the [philosophy](../../.claude/CLAUDE.md#philosophy).

The mark is monochrome and drawn from two plain paths, with no masks or effects, so it renders the same everywhere, down to a 16 px favicon.

| File | Use |
|---|---|
| [shosai-mark.svg](shosai-mark.svg) | The mark alone. Fills with `currentColor`, so it follows the theme. In the cabinet: `ShosaiMark` in `frontend/src/components/shosai-mark.tsx`. |
| [shosai-lockup.svg](shosai-lockup.svg) | Mark with the wordmark. The word is set in Geist SemiBold, shaped with kerning and converted to outlines, so it needs no font. |
| [shosai-icon.svg](shosai-icon.svg) | App icon on a rounded tile. Source of `frontend/public/icon.svg`, `icon-192.png`, `icon-512.png` and `favicon.ico`. |
| [shosai-icon-maskable.svg](shosai-icon-maskable.svg) | Full-bleed tile with the mark inside the maskable safe zone. Source of `icon-512-maskable.png`. |

## Colours

| Name | Value | Role |
|---|---|---|
| Ink | `#0A0A0A` | Mark on light backgrounds, icon tile |
| Paper | `#FAFAFA` | Mark on dark backgrounds and on the icon tile |

## Rules

- One colour only. Do not add gradients, shadows, outlines or a second colour.
- Keep clear space around the mark of at least half its width.
- Do not change the gap between the panels or their proportions.
- Below 24 px on a busy background use the icon tile, not the bare mark.
- When the mark changes, regenerate the PNG and ICO files in `frontend/public/` from the SVGs here.

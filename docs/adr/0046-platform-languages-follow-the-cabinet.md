# ADR 0046 — Platform languages follow the cabinet

- **Status:** accepted by the owner on 2026-10-14 (identity slice plan, decision ID-D3).
- **Package:** `identity` step 6 (core `LOCALES`, email texts, `/v1/auth/me.language`); every later slice with user-facing text.
- **Context documents:** [identity plan](../plan/slices/identity.md) ID-D3; [ADR 0022](0022-new-web-design-replaces-draft-parity.md); `frontend/src/lib/language.ts`; `backend/src/shosai/core/i18n/locales.py`.

## Context

- The cabinet's 16 interface languages are `en, fr, de, ru, nl, it, es, pt-BR, ar, tr, ko, hi, vi, zh-Hant, ja, id`.
- Core, the draft and the shipped native clients use `th` instead of `nl`, and the codes `pt` and `zh`. Core's set also drives the 16-language email texts.
- Two sets mean a person can choose a language in the cabinet that their emails and their desktop app do not know.

## Decision

1. **The cabinet's set is the platform's set**, with the cabinet's codes. The new web design is the product reference (ADR 0022).
2. **Core changes `th` to `nl`.** `core/i18n/locales.py` and every email template follow, with Dutch texts and no Thai ones. This happens in identity's step 6, together with the stored interface language.
3. **The native `GET /v1/auth/me.language` maps:**
   - `pt-BR` → `pt`;
   - `zh-Hant` → `zh`;
   - `nl` → `null`, which the shipped desktop clients read as "use the system language".

## Alternatives

- **Add Thai to the cabinet and drop Dutch.** Rejected: the cabinet's 65 namespaces would need Thai, and the product reference chose Dutch.
- **Seventeen languages.** Rejected: the platform promises 16, and every catalogue would grow.

## Consequences

- Thai readers of the draft's emails get English until a 17th language is decided.
- Dutch users of the shipped desktop apps see their system language.
- A language is one code across the cabinet, the API, emails and Leo's answer language.

## Revisit when

- Product data shows demand for Thai, or the native clients ship Dutch.

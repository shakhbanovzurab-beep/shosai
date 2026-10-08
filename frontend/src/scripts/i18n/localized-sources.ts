/**
 * Source that is fully localized, so the i18n check (`npm test`) holds it to the source rules (no hardcoded copy,
 * no physical direction classes, no fixed locales, mirrored arrows). A folder ends with "/". The list only
 * grows: each localization phase adds what it finished. The admin panel (Russian only) never joins it.
 */
export const LOCALIZED_SOURCES = [
  "src/i18n/",
  "src/hooks/use-ui-language.ts",
  "src/hooks/use-switch-language.ts",
  "src/components/feedback.tsx",
  "src/components/name-dialog.tsx",
  "src/features/shell/",
  "src/features/preferences/ui/layout-controls.tsx",
  "src/features/preferences/ui/preference-toggle.tsx",
  "src/features/leo/",
  "src/features/kanban/",
  "src/features/settings/",
  "src/features/studio/",
  "src/features/productivity/",
  "src/features/notes/",
  "src/features/meetings/",
  "src/features/hub/",
  "src/features/workspace/domain/",
  "src/features/workspace/api/",
  "src/features/workspace/model/",
  "src/features/workspace/mocks/",
  "src/features/workspace/ui/members/",
  "src/features/workspace/ui/settings/",
  "src/features/workspace/ui/switcher/",
  "src/features/workspace/ui/onboarding/",
  "src/features/workspace/ui/shared/",
  "src/features/workspace/ui/home/",
  "src/features/workspace/ui/knowledge/",
  "src/features/workspace/ui/decisions/",
  "src/features/workspace/ui/projects/",
  "src/features/workspace/ui/meetings/",
  "src/features/workspace/ui/tasks/",
  "src/features/workspace/ui/personal/",
  "src/features/file-manager/",
  "src/features/knowledge-base/",
  "src/features/calendar/",
  "src/features/upgrade/",
  "src/features/download/",
  "src/features/mail/",
  "src/features/support/",
  "src/components/page-placeholder.tsx",
  "src/components/filter-select.tsx",
  "src/components/meta-item.tsx",
  "src/components/emoji/",
  "src/app/pages/user/",
  "src/app/pages/workspace/",
  "src/app/pages/standalone/",
  "src/app/errors/",
  "src/app/root/",
  "src/app/layouts/",
  "src/lib/navigation.tsx",
];

/**
 * Inside the localized source, files written for the admin panel only. It is Russian by design and never
 * translated, so its text stays in code (see docs/i18n.md).
 */
export const ADMIN_ONLY_SOURCES = [
  "src/features/shell/ui/admin-navigation.ts",
  "src/features/leo/domain/admin-suggestions.ts",
  "src/features/workspace/mocks/control.ts",
];

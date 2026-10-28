import { handlers as adminApps } from "@/features/admin-apps/mocks/handlers";
import { handlers as adminBilling } from "@/features/admin-billing/mocks/handlers";
import { handlers as adminErrors } from "@/features/admin-errors/mocks/handlers";
import { handlers as adminLivekit } from "@/features/admin-livekit/mocks/handlers";
import { handlers as adminPlans } from "@/features/admin-plans/mocks/handlers";
import { handlers as adminSupport } from "@/features/admin-support/mocks/handlers";
import { handlers as adminUsers } from "@/features/admin-users/mocks/handlers";
import { handlers as adminWorkspaces } from "@/features/admin-workspaces/mocks/handlers";
import { handlers as chats } from "@/features/chats/mocks/handlers";
import { handlers as fileManager } from "@/features/file-manager/mocks/handlers";
import { handlers as hub } from "@/features/hub/mocks/handlers";
import { handlers as identity } from "@/features/identity/mocks/handlers";
import { handlers as knowledgeBase } from "@/features/knowledge-base/mocks/handlers";
import { handlers as leo } from "@/features/leo/mocks/handlers";
import { handlers as mail } from "@/features/mail/mocks/handlers";
import { handlers as meetings } from "@/features/meetings/mocks/handlers";
import { handlers as settings } from "@/features/settings/mocks/handlers";
import { handlers as studio } from "@/features/studio/mocks/handlers";
import { handlers as support } from "@/features/support/mocks/handlers";
import { handlers as upgrade } from "@/features/upgrade/mocks/handlers";
import { handlers as workspace } from "@/features/workspace/mocks/handlers";

import type { MockRoute } from "./routing";

/** Примерные маршруты всех слайсов. Слайс убирает свою строку вместе с обработчиками, когда появляется его API. */
export const mockRoutes: readonly MockRoute[] = [
  ...adminApps,
  ...adminBilling,
  ...adminErrors,
  ...adminLivekit,
  ...adminPlans,
  ...adminSupport,
  ...adminUsers,
  ...adminWorkspaces,
  ...chats,
  ...fileManager,
  ...hub,
  ...identity,
  ...knowledgeBase,
  ...leo,
  ...mail,
  ...meetings,
  ...settings,
  ...studio,
  ...support,
  ...upgrade,
  ...workspace,
];

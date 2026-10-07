import { apiRequest } from "@/lib/api-client";

import type { MailInsightsResponse } from "../domain/leo-insights";

export const insightsApi = {
  list: () => apiRequest<MailInsightsResponse>("/api/mail/insights"),
};

export type { LatestRelease as PublicAppRelease } from "./domain/contract";
export { latestRelease as latestPublishedRelease } from "./server/demo-store";
export { latestAppReleaseRoute } from "./server/latest-route";
export { appReleaseDownloadRoute, appReleaseRoute, appReleasesRoute } from "./server/releases-route";

import { type MockRoute, mockRoute } from "@/mocks/routing";

import { demoBucketRoute, uploadCompleteRoute, uploadRoute, uploadsRoute } from "./demo-uploads";
import {
  demoFileBytesRoute,
  fileCopyRoute,
  fileDownloadRoute,
  fileReindexRoute,
  fileRoute,
  filesRoute,
  storageRoute,
} from "./files-route";
import { folderRoute, foldersRoute } from "./folders-route";

/** The files API of `npm run dev` and the tests, on the backend's `/v1` paths, with a stand-in bucket. */
export const handlers: MockRoute[] = [
  mockRoute("/v1/files", filesRoute, ["GET", "POST"]),
  mockRoute("/v1/files/storage", storageRoute, ["GET"]),
  mockRoute("/v1/files/folders", foldersRoute, ["POST"]),
  mockRoute("/v1/files/folders/:id", folderRoute, ["PATCH", "DELETE"]),
  mockRoute("/v1/files/:id", fileRoute, ["PATCH", "DELETE"]),
  mockRoute("/v1/files/:id/copy", fileCopyRoute, ["POST"]),
  mockRoute("/v1/files/:id/reindex", fileReindexRoute, ["POST"]),
  mockRoute("/v1/files/:id/download", fileDownloadRoute, ["GET"]),
  mockRoute("/v1/me/uploads", uploadsRoute, ["POST"]),
  mockRoute("/v1/me/uploads/:id", uploadRoute, ["GET", "DELETE"]),
  mockRoute("/v1/me/uploads/:id/complete", uploadCompleteRoute, ["POST"]),
  mockRoute("/demo-bucket/:id/:part", demoBucketRoute, ["PUT"]),
  mockRoute("/demo-files/:id", demoFileBytesRoute, ["GET"]),
];

/*
 * Google Picker: человек сам выбирает в окне Google файлы и папки Диска, к которым получит доступ проект Shosai
 * (`drive.file`). Скрипты Google (`api.js` Picker и клиент Google Identity Services) грузятся только по требованию —
 * `preloadGooglePicker` зовут, когда человек тянется к выбору, `pickDriveFiles` — по нажатию. Токен браузер берёт
 * у Google сам и никуда не отправляет: серверу Shosai достаточно того, что выбранное открыто проекту.
 */

const PICKER_SCRIPT = "https://apis.google.com/js/api.js";
const IDENTITY_SCRIPT = "https://accounts.google.com/gsi/client";
const DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file";

/** What the server gives the cabinet to open the Picker with. */
export type GooglePickerSetup = {
  developerKey: string;
  appId: string;
  clientId: string;
  loginHint: string | null;
};

export type PickedFile = { id: string; name: string; mimeType: string };

type TokenAnswer = { access_token?: string; error?: string };
type TokenClient = { requestAccessToken: (options?: { prompt?: string }) => void };
type PickerAnswer = { action: string; docs?: PickedFile[] };
type DocsView = {
  setIncludeFolders: (value: boolean) => DocsView;
  setSelectFolderEnabled: (value: boolean) => DocsView;
};
type PickerBuilder = {
  setDeveloperKey: (key: string) => PickerBuilder;
  setAppId: (id: string) => PickerBuilder;
  setOAuthToken: (token: string) => PickerBuilder;
  addView: (view: DocsView) => PickerBuilder;
  enableFeature: (feature: string) => PickerBuilder;
  setCallback: (callback: (answer: PickerAnswer) => void) => PickerBuilder;
  build: () => { setVisible: (visible: boolean) => void };
};
type GoogleNamespace = {
  accounts: {
    oauth2: {
      initTokenClient: (config: {
        client_id: string;
        scope: string;
        login_hint?: string;
        callback: (answer: TokenAnswer) => void;
        error_callback: (error: { type: string }) => void;
      }) => TokenClient;
    };
  };
  picker: {
    DocsView: new () => DocsView;
    PickerBuilder: new () => PickerBuilder;
    Feature: { MULTISELECT_ENABLED: string };
  };
};
type GoogleWindow = Window & {
  gapi?: { load: (name: string, options: { callback: () => void; onerror: () => void }) => void };
  google?: GoogleNamespace;
};

const scripts = new Map<string, Promise<void>>();

function loadScript(src: string): Promise<void> {
  const known = scripts.get(src);
  if (known !== undefined) return known;
  const loading = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scripts.delete(src);
      reject(new Error(`Google script did not load: ${src}`));
    };
    document.head.append(script);
  });
  scripts.set(src, loading);
  return loading;
}

let pickerReady: Promise<GoogleNamespace> | null = null;

/** Loads Google's Picker and Identity Services once; later calls get the same promise. */
export function preloadGooglePicker(): Promise<GoogleNamespace> {
  pickerReady ??= Promise.all([loadScript(PICKER_SCRIPT), loadScript(IDENTITY_SCRIPT)])
    .then(
      () =>
        new Promise<GoogleNamespace>((resolve, reject) => {
          const page = window as GoogleWindow;
          page.gapi?.load("picker", {
            callback: () => (page.google ? resolve(page.google) : reject(new Error("Google Picker is missing"))),
            onerror: () => reject(new Error("Google Picker did not load")),
          });
        }),
    )
    .catch((error: unknown) => {
      pickerReady = null;
      throw error;
    });
  return pickerReady;
}

function driveToken(google: GoogleNamespace, setup: GooglePickerSetup): Promise<string> {
  return new Promise((resolve, reject) => {
    const client = google.accounts.oauth2.initTokenClient({
      client_id: setup.clientId,
      scope: DRIVE_FILE_SCOPE,
      login_hint: setup.loginHint ?? undefined,
      callback: (answer) =>
        answer.access_token ? resolve(answer.access_token) : reject(new Error(answer.error ?? "no token")),
      error_callback: (error) => reject(new Error(error.type)),
    });
    client.requestAccessToken({ prompt: "" });
  });
}

/** Opens Google's Picker; the files and folders the person chose, or null when they closed it. */
export async function pickDriveFiles(setup: GooglePickerSetup): Promise<PickedFile[] | null> {
  const google = await preloadGooglePicker();
  const token = await driveToken(google, setup);
  return new Promise((resolve) => {
    const view = new google.picker.DocsView().setIncludeFolders(true).setSelectFolderEnabled(true);
    new google.picker.PickerBuilder()
      .setDeveloperKey(setup.developerKey)
      .setAppId(setup.appId)
      .setOAuthToken(token)
      .addView(view)
      .enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
      .setCallback((answer) => {
        if (answer.action === "picked") resolve(answer.docs ?? []);
        else if (answer.action === "cancel") resolve(null);
      })
      .build()
      .setVisible(true);
  });
}

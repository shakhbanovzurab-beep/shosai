// Заглушки сторонних виджетов входа.
//
// Кнопки Яндекса, VK и Google в бою рисуют сами провайдеры — своими скриптами и
// в своих iframe. На стенде внешние хосты закрыты, и черновик, не дождавшись
// SDK, показывает тост «Не удалось войти через сервис» — его у пользователей
// нет. Пиксели чужих виджетов к паритету не относятся: v2 встраивает те же SDK.
// Поэтому вместо внешних скриптов отдаются заглушки: SDK «загружается», ничего
// не рисует и ждёт нажатия, которого не будет. Место под кнопку обе цели
// оставляют одинаковым, а лишнего тоста нет.
//
// Всё, что здесь не перечислено, на внешних хостах отклоняется.

export interface StubResponse {
  readonly contentType: string;
  readonly body: string;
}

const YANDEX_SUGGEST: StubResponse = {
  contentType: "text/javascript",
  body: "window.YaAuthSuggest={init:function(){return Promise.resolve({handler:function(){return new Promise(function(){});}});}};",
};

const GOOGLE_IDENTITY: StubResponse = {
  contentType: "text/javascript",
  body: "window.google={accounts:{id:{initialize:function(){},renderButton:function(){},prompt:function(){},cancel:function(){},disableAutoSelect:function(){}}}};",
};

/**
 * Документ iframe VK ID: пустой, но сообщает SDK, что загрузился. Без этого
 * сообщения (протокол моста @vkid/sdk 2.6: тип `vk-sak-sdk`, обработчик
 * `common: load`) SDK через 5 с объявляет ошибку по таймауту, и черновик
 * показывает тост о сбое входа.
 */
const VK_FRAME: StubResponse = {
  contentType: "text/html; charset=utf-8",
  body:
    "<!doctype html><html><head><title>VK ID</title></head><body>" +
    '<script>parent.postMessage({type:"vk-sak-sdk",handler:"common: load",params:{}},"*");</script>' +
    "</body></html>",
};

export function thirdPartyStub(url: URL): StubResponse | null {
  if (url.host === "yastatic.net" && url.pathname.startsWith("/s3/passport-sdk/autofill/")) return YANDEX_SUGGEST;
  if (url.host === "accounts.google.com" && url.pathname === "/gsi/client") return GOOGLE_IDENTITY;
  if (url.host === "id.vk.com") return VK_FRAME;
  return null;
}

import { CameraOff, Mic, MicOff, RefreshCw, Video, VideoOff } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";

import type { LocalMedia } from "../../model/local-media";
import { DeviceMenu } from "./device-menu";

/** Свой кадр в лобби: камера зеркально, без звука; объяснение, если браузер не дал устройства. */
export function SelfPreview({ media }: { media: LocalMedia }) {
  const t = useTranslations("meetingRoom");
  const showVideo = media.access === "ready" && media.camera;
  return (
    <div className="flex flex-col gap-3">
      <div className="relative aspect-video overflow-hidden rounded-xl bg-muted">
        {showVideo ? (
          <video
            ref={(element) => {
              if (element && element.srcObject !== media.stream) element.srcObject = media.stream;
            }}
            autoPlay
            muted
            playsInline
            className="size-full -scale-x-100 object-cover"
          />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-3 p-6 text-center">
            <CameraOff aria-hidden="true" className="size-8 text-muted-foreground" />
            <p className="max-w-xs text-muted-foreground text-sm">
              {t(`preview.${media.access === "ready" ? "cameraOff" : media.access}`)}
            </p>
            {media.access === "blocked" ? (
              <Button variant="outline" size="sm" onClick={media.retry}>
                <RefreshCw data-icon="inline-start" />
                {t("preview.retry")}
              </Button>
            ) : null}
          </div>
        )}
      </div>
      <div className="flex items-center justify-center gap-2">
        <Toggle
          variant="outline"
          pressed={media.mic}
          onPressedChange={media.setMic}
          disabled={media.access !== "ready"}
          aria-label={t("controls.mic")}
        >
          {media.mic ? <Mic aria-hidden="true" /> : <MicOff aria-hidden="true" />}
        </Toggle>
        <Toggle
          variant="outline"
          pressed={media.camera}
          onPressedChange={media.setCamera}
          disabled={media.access !== "ready"}
          aria-label={t("controls.camera")}
        >
          {media.camera ? <Video aria-hidden="true" /> : <VideoOff aria-hidden="true" />}
        </Toggle>
        <DeviceMenu media={media} />
      </div>
    </div>
  );
}

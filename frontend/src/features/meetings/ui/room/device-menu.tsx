import { useId } from "react";

import { Settings2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import type { DeviceChoice, LocalMedia } from "../../model/local-media";

/** Выбор микрофона и камеры; браузер называет устройства только после разрешения. */
export function DeviceMenu({ media }: { media: LocalMedia }) {
  const t = useTranslations("meetingRoom");
  const id = useId();
  const lists: [keyof DeviceChoice, MediaDeviceInfo[]][] = [
    ["audio", media.microphones],
    ["video", media.cameras],
  ];
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon" disabled={media.access !== "ready"} aria-label={t("devices.open")}>
          <Settings2 aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72">
        <FieldGroup>
          {lists.map(([kind, devices]) => (
            <Field key={kind}>
              <FieldLabel htmlFor={`${id}-${kind}`}>{t(`devices.${kind}`)}</FieldLabel>
              <NativeSelect
                id={`${id}-${kind}`}
                value={media.choice[kind] ?? devices[0]?.deviceId ?? ""}
                onChange={(event) => media.choose(kind, event.target.value)}
              >
                {devices.map((device, index) => (
                  <NativeSelectOption key={device.deviceId} value={device.deviceId}>
                    {device.label || t("devices.unnamed", { index: index + 1 })}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </Field>
          ))}
        </FieldGroup>
      </PopoverContent>
    </Popover>
  );
}

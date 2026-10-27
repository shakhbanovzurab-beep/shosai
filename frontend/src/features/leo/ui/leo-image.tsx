"use client";

import { type ImageArtifact, operatorImageUrl } from "../domain/artifacts";

/**
 * Картинка, нарисованная Leo оператору (agent шаг 16b2). Размеры из артефакта занимают место до загрузки — ответ
 * не прыгает; по нажатию картинка открывается целиком. Подпись видна под ней, а читалке хватает `alt`.
 */
export function LeoImage({ image }: { image: ImageArtifact }) {
  const src = operatorImageUrl(image.ref);
  return (
    <figure className="flex max-w-full flex-col gap-1.5">
      <a
        href={src}
        target="_blank"
        rel="noopener noreferrer"
        className="block w-fit max-w-full overflow-hidden rounded-lg border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <img
          src={src}
          alt={image.alt}
          width={image.width}
          height={image.height}
          loading="lazy"
          decoding="async"
          className="block h-auto max-h-96 w-auto max-w-full object-contain"
        />
      </a>
      <figcaption className="text-muted-foreground text-xs" aria-hidden="true">
        {image.alt}
      </figcaption>
    </figure>
  );
}

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CONTENT_GLYPHS } from "@/core/ui/icon/glyphsContent";
import { INTERFACE_GLYPHS } from "@/core/ui/icon/glyphsInterface";
import { MEDIA_GLYPHS } from "@/core/ui/icon/glyphsMedia";
import { Icon, type IconName } from "@/core/ui/icon/Icon";
import { Logo } from "@/core/ui/Logo";
import { SidebarGlyph } from "@/core/ui/SidebarGlyph";

const GROUPS = [INTERFACE_GLYPHS, CONTENT_GLYPHS, MEDIA_GLYPHS];
const NAMES = GROUPS.flatMap((group) => Object.keys(group)) as IconName[];
const MIRRORED: readonly IconName[] = ["chevron", "chevronLeft", "arrowLeft", "send", "logout"];

const parse = (markup: string): SVGSVGElement => {
  const host = document.createElement("div");
  host.innerHTML = markup;
  const svg = host.firstElementChild;
  if (!(svg instanceof SVGSVGElement)) throw new Error(`Не SVG: ${markup.slice(0, 80)}`);
  return svg;
};

describe("иконки", () => {
  it("набор черновика целиком, без повторов имён между группами", () => {
    expect(NAMES).toHaveLength(90);
    expect(new Set(NAMES).size).toBe(NAMES.length);
  });

  it.each(NAMES)("%s рисуется глифом в сетке 24 × 24", (name) => {
    const markup = renderToStaticMarkup(<Icon name={name} />);
    const svg = parse(markup);
    expect(svg.getAttribute("viewBox")).toBe("0 0 24 24");
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.children.length).toBeGreaterThan(0);
    // Атрибуты SVG доходят до разметки в своём написании, а не как имена свойств JSX.
    expect(markup).not.toMatch(/\s(fillRule|strokeWidth|strokeLinecap|strokeLinejoin)=/);
  });

  it("размер в em от кегля строки, обводка и класс вызывающего", () => {
    const svg = parse(renderToStaticMarkup(<Icon name="search" size={20} stroke={2} className="inline text-faint" />));
    expect(svg.getAttribute("width")).toBe("1.25em");
    expect(svg.getAttribute("height")).toBe("1.25em");
    expect(svg.getAttribute("stroke-width")).toBe("2");
    // block выигрывает у display-класса вызывающего, остальные классы остаются.
    expect(svg.getAttribute("class")).toBe("text-faint block");
  });

  it("в письме справа налево отражаются ровно глифы направления чтения", () => {
    for (const name of NAMES) {
      const mirrored = parse(renderToStaticMarkup(<Icon name={name} />)).classList.contains("rtl-mirror");
      expect(mirrored, name).toBe(MIRRORED.includes(name));
    }
  });

  it("знак Leo залит по правилу evenodd", () => {
    const path = parse(renderToStaticMarkup(<Icon name="leo" />)).querySelector("path");
    expect(path?.getAttribute("fill-rule")).toBe("evenodd");
  });
});

describe("логотип и глиф сайдбара", () => {
  it("логотип — девять плиток WHISPERER с подписью для чтения с экрана", () => {
    const svg = parse(renderToStaticMarkup(<Logo size={32} />));
    expect(svg.getAttribute("role")).toBe("img");
    expect(svg.getAttribute("aria-label")).toBe("Whisperer");
    expect(svg.getAttribute("width")).toBe("32");
    expect(svg.querySelectorAll("rect")).toHaveLength(9);
    expect([...svg.querySelectorAll("text")].map((text) => text.textContent).join("")).toBe("WHISPERER");
  });

  it("глиф сайдбара: стрелка только у «раскрыть» и «свернуть»", () => {
    const arrow = (variant: "plain" | "expand" | "collapse") =>
      parse(renderToStaticMarkup(<SidebarGlyph variant={variant} size={26} />)).querySelector("polyline");
    expect(arrow("plain")).toBeNull();
    expect(arrow("expand")?.getAttribute("points")).toBe("10,6.6 13.5,9 10,11.4");
    expect(arrow("collapse")?.getAttribute("points")).toBe("12.5,11.4 9,9 12.5,6.6");
    expect(parse(renderToStaticMarkup(<SidebarGlyph variant="plain" size={26} />)).getAttribute("width")).toBe(
      "1.625em",
    );
  });
});

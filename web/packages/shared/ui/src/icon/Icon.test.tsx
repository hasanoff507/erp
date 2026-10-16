import { render } from "@testing-library/react";
import { ScanLine } from "lucide-react";
import { describe, expect, it } from "vitest";

import { initialsOf } from "../composites/identity.tsx";
import { cn } from "../lib/cn.ts";

import { Icon } from "./Icon.tsx";

describe("Icon — 24 §4.2", () => {
  it("defaults to strokeWidth 1.8, 18px and aria-hidden", () => {
    const { container } = render(<Icon as={ScanLine} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("stroke-width")).toBe("1.8");
    expect(svg?.getAttribute("width")).toBe("18");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
  });

  it("exposes an accessible name when labelled", () => {
    const { container } = render(<Icon as={ScanLine} size="xl" label="Skaner" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("aria-label")).toBe("Skaner");
    expect(svg?.getAttribute("aria-hidden")).toBeNull();
    expect(svg?.getAttribute("width")).toBe("24");
  });
});

describe("ui helpers", () => {
  it("cn keeps custom font-size tokens next to colour classes", () => {
    expect(cn("text-h1 text-foreground", "text-muted-foreground")).toBe("text-h1 text-muted-foreground");
    expect(cn("text-body", "text-h2")).toBe("text-h2");
  });

  it("initialsOf takes the first two words", () => {
    expect(initialsOf("Akmal Karimov")).toBe("AK");
    expect(initialsOf("  dilnoza ")).toBe("D");
  });
});

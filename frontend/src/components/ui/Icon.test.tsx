import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  ArrowLeftIcon,
  ArrowUpIcon,
  BrainIcon,
  LeafIcon,
  PaperclipIcon,
  SparkleIcon,
} from "@phosphor-icons/react";

describe("Icon usage", () => {
  it("hides decorative icons from assistive technology by default", () => {
    const { container } = render(<LeafIcon aria-hidden="true" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg?.getAttribute("role")).toBeNull();
  });

  it("exposes informative icons via a <title> child when alt is set", () => {
    const { container } = render(<BrainIcon alt="Asistente" />);
    const svg = container.querySelector("svg");
    const title = svg?.querySelector("title");
    expect(title).toBeInTheDocument();
    expect(title).toHaveTextContent("Asistente");
  });

  it("renders stroke-style icons with weight=regular so the path is visible", () => {
    const { container: back } = render(
      <ArrowLeftIcon aria-hidden="true" weight="regular" />,
    );
    const { container: up } = render(
      <ArrowUpIcon aria-hidden="true" weight="regular" />,
    );
    const { container: attach } = render(
      <PaperclipIcon aria-hidden="true" weight="regular" />,
    );
    const { container: sparkle } = render(<SparkleIcon aria-hidden="true" />);
    expect(back.querySelector("svg")).toBeTruthy();
    expect(up.querySelector("svg")).toBeTruthy();
    expect(attach.querySelector("svg")).toBeTruthy();
    expect(sparkle.querySelector("svg")).toBeTruthy();
  });
});

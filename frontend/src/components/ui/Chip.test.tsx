import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Chip } from "./Chip";

describe("Chip", () => {
  it("renders its label and tone modifier class", () => {
    render(<Chip tone="primary">Bosque</Chip>);
    const chip = screen.getByText("Bosque");
    expect(chip).toBeInTheDocument();
    expect(chip.parentElement?.className).toMatch(/tone-primary/);
  });

  it("hides decorative icons from assistive technology", () => {
    render(
      <Chip tone="secondary" icon={<span data-testid="icon">L</span>}>
        Tierra
      </Chip>,
    );
    const icon = screen.getByTestId("icon");
    expect(icon.closest('[aria-hidden="true"]')).toBeInTheDocument();
  });
});

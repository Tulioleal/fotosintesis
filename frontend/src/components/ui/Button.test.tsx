import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import NextLink from "next/link";
import { Button } from "./Button";

describe("Button", () => {
  it("renders its label and forwards click events", () => {
    let clicked = 0;
    render(<Button onClick={() => clicked++}>Guardar</Button>);

    const button = screen.getByRole("button", { name: "Guardar" });
    button.click();
    expect(clicked).toBe(1);
  });

  it("applies variant and size modifiers via class names", () => {
    render(
      <Button variant="secondary" size="sm" data-testid="btn">
        Editar
      </Button>,
    );
    const button = screen.getByTestId("btn");
    expect(button.className).toMatch(/variant-secondary/);
    expect(button.className).toMatch(/size-sm/);
  });

  it("marks decorative icons as aria-hidden while keeping the label visible", () => {
    render(
      <Button
        leadingIcon={<span data-testid="leading-icon">*</span>}
        trailingIcon={<span data-testid="trailing-icon">.</span>}
      >
        Continuar
      </Button>,
    );

    expect(screen.getByText("Continuar")).toBeInTheDocument();
    const leading = screen.getByTestId("leading-icon");
    const trailing = screen.getByTestId("trailing-icon");
    expect(leading.closest('[aria-hidden="true"]')).toBeInTheDocument();
    expect(trailing.closest('[aria-hidden="true"]')).toBeInTheDocument();
  });

  it("applies implicit type button only for native buttons", () => {
    const { rerender } = render(<Button>Guardar</Button>);
    expect(screen.getByRole("button", { name: "Guardar" })).toHaveAttribute(
      "type",
      "button",
    );

    rerender(
      <Button as="a" href="/garden">
        Mi Jardín
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Mi Jardín" });
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/garden");
    expect(link).not.toHaveAttribute("type");
  });

  it("supports rendering as a Next.js Link", () => {
    render(
      <Button as={NextLink} href="/identify" variant="primary">
        Identificar
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Identificar" });
    expect(link).toHaveAttribute("href", "/identify");
    expect(link.className).toMatch(/variant-primary/);
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ArrowRightIcon } from "@phosphor-icons/react";
import { AppLink } from "./AppLink";

describe("AppLink", () => {
  it("renders internal links with the provided href", () => {
    render(<AppLink href="/garden">Mi Jardín</AppLink>);
    const link = screen.getByRole("link", { name: "Mi Jardín" });
    expect(link).toHaveAttribute("href", "/garden");
  });

  it("renders external links with target and rel attributes", () => {
    render(
      <AppLink href="https://example.com" external>
        Fuente externa
      </AppLink>,
    );
    const link = screen.getByRole("link", { name: "Fuente externa" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
    expect(link).toHaveAttribute("href", "https://example.com");
  });

  it("auto-detects external links from the href", () => {
    render(<AppLink href="https://example.com/page">Externo</AppLink>);
    const link = screen.getByRole("link", { name: "Externo" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("applies button variant classes when variant is button", () => {
    render(
      <AppLink href="/identify" variant="button" buttonVariant="primary">
        Registrar Planta
      </AppLink>,
    );
    const link = screen.getByRole("link", { name: "Registrar Planta" });
    expect(link.className).toMatch(/variant-primary/);
    expect(link.className).toMatch(/size-md/);
  });

  it("hides decorative icons from assistive technology", () => {
    render(
      <AppLink
        href="/garden"
        trailingIcon={<ArrowRightIcon aria-hidden="true" size="1rem" weight="bold" data-testid="trailing" />}
      >
        Ver todas
      </AppLink>,
    );
    const icon = screen.getByTestId("trailing");
    expect(icon.closest('[aria-hidden="true"]')).toBeInTheDocument();
  });
});

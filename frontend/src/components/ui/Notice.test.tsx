import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Notice } from "./Notice";

describe("Notice", () => {
  it("uses status role for informational notices", () => {
    render(<Notice tone="info">Información útil</Notice>);
    expect(screen.getByRole("status")).toHaveTextContent("Información útil");
  });

  it("uses alert role for error notices", () => {
    render(
      <Notice tone="error" heading="Algo falló">
        Probá de nuevo en unos minutos.
      </Notice>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Algo falló");
    expect(alert).toHaveTextContent("Probá de nuevo en unos minutos.");
  });
});

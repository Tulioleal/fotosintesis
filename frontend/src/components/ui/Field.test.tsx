import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Field, SelectField, TextareaField } from "./Field";

describe("Field", () => {
  it("renders label, hint, and accessible associations", () => {
    render(<Field label="Correo" hint="Usá un correo válido" name="email" />);

    const input = screen.getByLabelText("Correo") as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.getAttribute("aria-describedby")).toMatch(/-hint$/);
  });

  it("marks invalid state and links to error text", () => {
    render(
      <Field
        label="Correo"
        error="Formato inválido"
        name="email"
        defaultValue="foo"
      />,
    );
    const input = screen.getByLabelText("Correo") as HTMLInputElement;
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-errormessage")).toMatch(/-error$/);
    expect(screen.getByRole("alert")).toHaveTextContent("Formato inválido");
  });

  it("renders a textarea variant with proper association", () => {
    render(
      <TextareaField
        kind="textarea"
        label="Notas"
        hint="Anotá lo que observaste"
        name="notes"
      />,
    );
    const textarea = screen.getByLabelText("Notas") as HTMLTextAreaElement;
    expect(textarea.tagName).toBe("TEXTAREA");
    expect(textarea.getAttribute("aria-describedby")).toMatch(/-hint$/);
  });

  it("renders a select variant with its options", () => {
    render(
      <SelectField kind="select" label="Especie" name="species">
        <option value="">Elegí una especie</option>
        <option value="monstera">Monstera</option>
      </SelectField>,
    );
    const select = screen.getByLabelText("Especie") as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    expect(select.options).toHaveLength(2);
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterForm } from "./RegisterForm";

const mocks = vi.hoisted(() => ({
  register: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    register: mocks.register,
  },
}));

describe("RegisterForm", () => {
  beforeEach(() => {
    mocks.register.mockClear();
  });

  it("renders validation-ready registration fields", () => {
    render(<RegisterForm />);
    expect(screen.getByLabelText("Nombre")).toBeInTheDocument();
    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear cuenta" })).toBeEnabled();
  });

  it("displays validation errors before submitting invalid registration input", async () => {
    render(<RegisterForm />);

    fireEvent.change(screen.getByLabelText("Correo"), {
      target: { value: "tuli@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "corta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));

    expect(await screen.findByText("Ingresá tu nombre.")).toBeInTheDocument();
    expect(screen.getByText("La contraseña debe tener al menos 8 caracteres.")).toBeInTheDocument();
    expect(mocks.register).not.toHaveBeenCalled();
  });
});

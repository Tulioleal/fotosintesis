import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterForm } from "./RegisterForm";

const mocks = vi.hoisted(() => ({
  register: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    register: mocks.register,
  },
}));

describe("RegisterForm", () => {
  beforeEach(() => {
    mocks.register.mockReset();
    mocks.push.mockReset();
  });

  it("renders validation-ready registration fields with their preserved accessible labels", () => {
    render(<RegisterForm />);
    expect(screen.getByLabelText("Nombre")).toBeInTheDocument();
    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear cuenta" })).toBeEnabled();
  });

  it("renders the disabled social login placeholder with clear semantics", () => {
    render(<RegisterForm />);

    const social = screen.getByRole("button", {
      name: /Continuar con Google próximamente/i,
    });
    expect(social).toBeDisabled();
    expect(social).toHaveAttribute("aria-disabled", "true");
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
    expect(
      screen.getByText("La contraseña debe tener al menos 8 caracteres."),
    ).toBeInTheDocument();
    expect(mocks.register).not.toHaveBeenCalled();
  });

  it("redirects to the login page with the registered-success notice after a successful registration", async () => {
    mocks.register.mockResolvedValue({ user: { id: "u-1" } });
    render(<RegisterForm />);

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Tuli" },
    });
    fireEvent.change(screen.getByLabelText("Correo"), {
      target: { value: "TULI@EXAMPLE.COM" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));

    await vi.waitFor(() => expect(mocks.register).toHaveBeenCalled());
    expect(mocks.register).toHaveBeenCalledWith({
      name: "Tuli",
      email: "tuli@example.com",
      password: "password123",
    });
    expect(mocks.push).toHaveBeenCalledWith("/login?registered=1");
  });

  it("shows a recoverable error message when the registration API fails", async () => {
    mocks.register.mockRejectedValueOnce(new Error("boom"));
    render(<RegisterForm />);

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Tuli" },
    });
    fireEvent.change(screen.getByLabelText("Correo"), {
      target: { value: "tuli@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));

    expect(
      await screen.findByText(
        "No pudimos crear la cuenta. Revisá los datos o intentá con otro correo.",
      ),
    ).toBeInTheDocument();
    expect(mocks.push).not.toHaveBeenCalled();
  });
});

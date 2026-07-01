import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "./LoginForm";

const mocks = vi.hoisted(() => ({
  signIn: vi.fn(),
  getParam: vi.fn<(key: string) => string | null>(),
}));

vi.mock("next-auth/react", () => ({
  signIn: mocks.signIn,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: mocks.getParam }),
}));

describe("LoginForm", () => {
  beforeEach(() => {
    mocks.signIn.mockReset();
    mocks.getParam.mockImplementation((key: string) => {
      if (key === "callbackUrl") return "/garden";
      return null;
    });
  });

  it("renders login fields with their preserved accessible labels", () => {
    render(<LoginForm />);

    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeEnabled();
  });

  it("renders the disabled social login placeholder with clear semantics", () => {
    render(<LoginForm />);

    const social = screen.getByRole("button", {
      name: /Continuar con Google próximamente/i,
    });
    expect(social).toBeDisabled();
    expect(social).toHaveAttribute("aria-disabled", "true");
  });

  it("submits credentials through Auth.js and displays sign-in failures", async () => {
    mocks.signIn.mockResolvedValue({ error: "CredentialsSignin" });
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText("Correo"), {
      target: { value: "TULI@EXAMPLE.COM" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(
      await screen.findByText(
        "No pudimos iniciar sesión con esos datos. Revisalos e intentá otra vez.",
      ),
    ).toBeInTheDocument();
    expect(mocks.signIn).toHaveBeenCalledWith("credentials", {
      email: "tuli@example.com",
      password: "secret123",
      callbackUrl: "/garden",
      redirect: false,
    });
  });

  it("shows the registered-success notice when arriving from the registration flow", () => {
    mocks.getParam.mockImplementation((key: string) =>
      key === "registered" ? "1" : null,
    );
    render(<LoginForm />);

    expect(
      screen.getByText("Cuenta creada. Ya podés iniciar sesión."),
    ).toBeInTheDocument();
  });

  it("exposes the existing auth links for navigation", () => {
    render(<LoginForm />);

    expect(
      screen.getByRole("link", { name: "Olvidé mi contraseña" }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(
      screen.getByRole("link", { name: "Crear cuenta" }),
    ).toHaveAttribute("href", "/register");
  });
});

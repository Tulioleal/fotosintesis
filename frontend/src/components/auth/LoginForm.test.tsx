import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "./LoginForm";

const mocks = vi.hoisted(() => ({
  signIn: vi.fn(),
  getParam: vi.fn((key: string) => (key === "callbackUrl" ? "/garden" : null)),
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
    mocks.getParam.mockImplementation((key: string) =>
      key === "callbackUrl" ? "/garden" : null,
    );
  });

  it("renders login fields", () => {
    render(<LoginForm />);

    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ingresar" })).toBeEnabled();
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

    expect(await screen.findByText("No pudimos iniciar sesión con esos datos. Revisalos e intentá otra vez.")).toBeInTheDocument();
    expect(mocks.signIn).toHaveBeenCalledWith("credentials", {
      email: "tuli@example.com",
      password: "secret123",
      callbackUrl: "/garden",
      redirect: false,
    });
  });
});

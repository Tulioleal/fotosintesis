import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordForm } from "./ResetPasswordForm";

const mocks = vi.hoisted(() => ({
  confirmRecovery: vi.fn(async () => ({ status: "ok" })),
  getParam: vi.fn<(key: string) => string | null>(),
  ApiClientError: class extends Error {
    status: number;
    constructor(status: number, message = "boom") {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock("@/lib/api/client", () => ({
  ApiClientError: mocks.ApiClientError,
  apiClient: {
    confirmRecovery: mocks.confirmRecovery,
  },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: mocks.getParam }),
}));

describe("ResetPasswordForm", () => {
  beforeEach(() => {
    mocks.confirmRecovery.mockClear();
    mocks.getParam.mockImplementation((key: string) => {
      if (key === "token") return "secret-token-value";
      return null;
    });
  });

  it("renders new-password and confirmation fields with accessible labels", () => {
    render(<ResetPasswordForm />);

    expect(screen.getByLabelText("Nueva contraseña")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirmar contraseña")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Actualizar contraseña" }),
    ).toBeEnabled();
  });

  it("does not display the token in page copy", () => {
    render(<ResetPasswordForm />);

    expect(screen.queryByText(/secret-token-value/)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("secret-token-value")).not.toBeInTheDocument();
  });

  it("validates matching passwords and submits the token and new password", async () => {
    render(<ResetPasswordForm />);

    fireEvent.change(screen.getByLabelText("Nueva contraseña"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "newpassword123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Actualizar contraseña" }));

    expect(
      await screen.findByText(/Si el enlace era válido/),
    ).toBeInTheDocument();
    expect(mocks.confirmRecovery).toHaveBeenCalledWith({
      token: "secret-token-value",
      password: "newpassword123",
    });
  });

  it("rejects mismatched confirmation with an accessible error", async () => {
    render(<ResetPasswordForm />);

    fireEvent.change(screen.getByLabelText("Nueva contraseña"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "different" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Actualizar contraseña" }));

    expect(
      await screen.findByText("Las contraseñas no coinciden."),
    ).toBeInTheDocument();
    expect(mocks.confirmRecovery).not.toHaveBeenCalled();
  });

  it("offers a path back to login and to request a new link", () => {
    render(<ResetPasswordForm />);

    expect(
      screen.getByRole("link", { name: "Volver a ingresar" }),
    ).toHaveAttribute("href", "/login");
    expect(
      screen.getByRole("link", { name: "Solicitar un enlace nuevo" }),
    ).toHaveAttribute("href", "/forgot-password");
  });

  it("stays neutral even when the request fails or is rate limited", async () => {
    mocks.confirmRecovery.mockRejectedValueOnce(new mocks.ApiClientError(429));
    render(<ResetPasswordForm />);

    fireEvent.change(screen.getByLabelText("Nueva contraseña"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "newpassword123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Actualizar contraseña" }));

    expect(
      await screen.findByText(/Si el enlace era válido/),
    ).toBeInTheDocument();
  });
});

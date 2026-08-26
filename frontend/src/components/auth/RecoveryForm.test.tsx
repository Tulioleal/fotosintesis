import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecoveryForm } from "./RecoveryForm";

const mocks = vi.hoisted(() => ({
  requestRecovery: vi.fn(async () => ({
    message: "Si el correo existe, te enviaremos instrucciones.",
  })),
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
    requestRecovery: mocks.requestRecovery,
  },
}));

describe("RecoveryForm", () => {
  beforeEach(() => {
    mocks.requestRecovery.mockClear();
  });

  it("renders the recovery email field with its preserved accessible label", () => {
    render(<RecoveryForm />);

    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Recuperar acceso" }),
    ).toBeEnabled();
  });

  it("submits recovery requests and displays the neutral confirmation message", async () => {
    render(<RecoveryForm />);

    fireEvent.change(screen.getByLabelText("Correo"), {
      target: { value: "TULI@EXAMPLE.COM" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Recuperar acceso" }));

    expect(
      await screen.findByText(
        "Si el correo existe, te enviaremos instrucciones.",
      ),
    ).toBeInTheDocument();
    expect(mocks.requestRecovery).toHaveBeenCalledWith({
      email: "tuli@example.com",
    });
  });

  it("exposes a link back to the login route", () => {
    render(<RecoveryForm />);

    expect(
      screen.getByRole("link", { name: "Volver a ingresar" }),
    ).toHaveAttribute("href", "/login");
  });

  it("shows the neutral recovery message and prevents resubmission when rate limited", async () => {
    mocks.requestRecovery.mockRejectedValueOnce(new mocks.ApiClientError(429));
    render(<RecoveryForm />);

    fireEvent.change(screen.getByLabelText("Correo"), {
      target: { value: "tuli@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Recuperar acceso" }));

    expect(
      await screen.findByText(
        "Si el correo existe en Fotosíntesis, vamos a preparar las instrucciones para que vuelvas a entrar.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recuperar acceso" })).toBeDisabled();
  });
});

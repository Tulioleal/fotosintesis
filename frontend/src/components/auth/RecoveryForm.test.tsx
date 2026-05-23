import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecoveryForm } from "./RecoveryForm";

const mocks = vi.hoisted(() => ({
  requestRecovery: vi.fn(async () => ({
    message: "Si el correo existe, te enviaremos instrucciones.",
  })),
}));

vi.mock("@/lib/generated/client", () => ({
  apiClient: {
    requestRecovery: mocks.requestRecovery,
  },
}));

describe("RecoveryForm", () => {
  beforeEach(() => {
    mocks.requestRecovery.mockClear();
  });

  it("renders the recovery email field", () => {
    render(<RecoveryForm />);

    expect(screen.getByLabelText("Correo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recuperar acceso" })).toBeEnabled();
  });

  it("submits recovery requests and displays the neutral message", async () => {
    render(<RecoveryForm />);

    fireEvent.change(screen.getByLabelText("Correo"), {
      target: { value: "TULI@EXAMPLE.COM" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Recuperar acceso" }));

    expect(await screen.findByText("Si el correo existe, te enviaremos instrucciones.")).toBeInTheDocument();
    expect(mocks.requestRecovery).toHaveBeenCalledWith({
      email: "tuli@example.com",
    });
  });
});

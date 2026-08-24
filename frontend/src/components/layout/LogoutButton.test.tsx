import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  signOut: vi.fn(),
  clear: vi.fn(),
}));

const callOrder: string[] = [];
mocks.signOut.mockImplementation(async () => {
  callOrder.push("signOut");
});
mocks.clear.mockImplementation(() => {
  callOrder.push("clear");
});

vi.mock("next-auth/react", () => ({
  signOut: mocks.signOut,
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ clear: mocks.clear }),
}));

import { LogoutButton } from "./LogoutButton";
import { render } from "@testing-library/react";

describe("LogoutButton", () => {
  beforeEach(() => {
    callOrder.length = 0;
    mocks.signOut.mockClear();
    mocks.clear.mockClear();
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
  });

  it("clears every cached query before signing out", async () => {
    render(<LogoutButton />);

    fireEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    await waitFor(() => {
      expect(mocks.signOut).toHaveBeenCalled();
    });
    // In-place account switching is not a supported flow (middleware redirects
    // unauthenticated requests); the whole cache is dropped instead of a fixed
    // set of namespaces.
    expect(callOrder).toEqual(["clear", "signOut"]);
    expect(mocks.clear).toHaveBeenCalledTimes(1);
    expect(mocks.signOut).toHaveBeenCalledWith({ redirectTo: "/login" });
  });
});

export type MockSession = {
  data: { user?: { id?: string } } | null;
  status: "loading" | "authenticated" | "unauthenticated";
};

export const TEST_USER_ID = "user-test-1111";

export const mockSessionState: MockSession = {
  data: { user: { id: TEST_USER_ID } },
  status: "authenticated",
};

export function setMockSessionUser(userId: string | undefined): void {
  mockSessionState.data = userId ? { user: { id: userId } } : null;
  mockSessionState.status = userId ? "authenticated" : "unauthenticated";
}

export function resetMockSession(): void {
  setMockSessionUser(TEST_USER_ID);
}

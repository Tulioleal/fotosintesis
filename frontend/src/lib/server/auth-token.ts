import { z } from "zod";

const parseableDate = z.string().refine((value) => !Number.isNaN(Date.parse(value)), {
  message: "value must be a valid date",
});

export const authTokenSchema = z.object({
  sub: z.string().min(1),
  backendCredential: z.string().min(1),
  sessionExpiresAt: parseableDate,
  email_verified: z.boolean(),
});

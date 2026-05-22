import { z } from "zod";

export const registerSchema = z.object({
  name: z.string().trim().min(1, "Ingresá tu nombre."),
  email: z.string().trim().email("Ingresá un correo válido.").transform((email) => email.toLowerCase()),
  password: z.string().min(8, "La contraseña debe tener al menos 8 caracteres."),
});

export const loginSchema = z.object({
  email: z.string().trim().email("Ingresá un correo válido.").transform((email) => email.toLowerCase()),
  password: z.string().min(1, "Ingresá tu contraseña."),
});

export const recoverySchema = z.object({
  email: z.string().trim().email("Ingresá un correo válido.").transform((email) => email.toLowerCase()),
});

export type RegisterFormValues = z.infer<typeof registerSchema>;
export type LoginFormValues = z.infer<typeof loginSchema>;
export type RecoveryFormValues = z.infer<typeof recoverySchema>;

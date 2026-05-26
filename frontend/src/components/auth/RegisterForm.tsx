"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { apiClient } from "@/lib/api/client";
import { authStyles } from "./AuthShell";
import { registerSchema, type RegisterFormValues } from "./auth-schemas";

export function RegisterForm() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  async function onSubmit(values: RegisterFormValues) {
    setFormError(null);
    try {
      await apiClient.register(values);
      router.push("/login?registered=1");
    } catch {
      setFormError(
        "No pudimos crear la cuenta. Revisá los datos o intentá con otro correo.",
      );
    }
  }

  return (
    <form className={authStyles.form} onSubmit={form.handleSubmit(onSubmit)}>
      <label className={authStyles.field}>
        Nombre
        <input
          autoComplete="name"
          disabled={form.formState.isSubmitting}
          {...form.register("name")}
        />
        {form.formState.errors.name && (
          <span className={authStyles.error}>
            {form.formState.errors.name.message}
          </span>
        )}
      </label>
      <label className={authStyles.field}>
        Correo
        <input
          autoComplete="email"
          disabled={form.formState.isSubmitting}
          type="email"
          {...form.register("email")}
        />
        {form.formState.errors.email && (
          <span className={authStyles.error}>
            {form.formState.errors.email.message}
          </span>
        )}
      </label>
      <label className={authStyles.field}>
        Contraseña
        <input
          autoComplete="new-password"
          disabled={form.formState.isSubmitting}
          type="password"
          {...form.register("password")}
        />
        {form.formState.errors.password && (
          <span className={authStyles.error}>
            {form.formState.errors.password.message}
          </span>
        )}
      </label>
      {formError && <p className={authStyles.error}>{formError}</p>}
      <div className={authStyles.actions}>
        <button
          className={authStyles.primary}
          disabled={form.formState.isSubmitting}
          type="submit"
        >
          {form.formState.isSubmitting ? "Creando cuenta..." : "Crear cuenta"}
        </button>
        <button className={authStyles.disabledSocial} disabled type="button">
          Continuar con Google próximamente
        </button>
      </div>
      <p className={authStyles.links}>
        <Link href="/login">Ya tengo cuenta</Link>
      </p>
    </form>
  );
}

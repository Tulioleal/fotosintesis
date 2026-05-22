"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { authStyles } from "./AuthShell";
import { loginSchema, type LoginFormValues } from "./auth-schemas";

export function LoginForm() {
  const params = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });
  const callbackUrl = params.get("callbackUrl") ?? "/home";

  async function onSubmit(values: LoginFormValues) {
    setFormError(null);
    const result = await signIn("credentials", {
      ...values,
      callbackUrl,
      redirect: false,
    });
    if (result?.error) {
      setFormError(
        "No pudimos iniciar sesión con esos datos. Revisalos e intentá otra vez.",
      );
      return;
    }
    window.location.assign(result?.url ?? callbackUrl);
  }

  return (
    <form className={authStyles.form} onSubmit={form.handleSubmit(onSubmit)}>
      {params.get("registered") && (
        <p>Cuenta creada. Ya podés iniciar sesión.</p>
      )}
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
          autoComplete="current-password"
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
          {form.formState.isSubmitting ? "Ingresando..." : "Ingresar"}
        </button>
        <button className={authStyles.disabledSocial} disabled type="button">
          Continuar con Google próximamente
        </button>
      </div>
      <p className={authStyles.links}>
        <Link href="/forgot-password">Olvidé mi contraseña</Link>
        <Link href="/register">Crear cuenta</Link>
      </p>
    </form>
  );
}

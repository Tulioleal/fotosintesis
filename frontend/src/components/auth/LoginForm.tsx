"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button, Field, Notice } from "@/components/ui";
import { authStyles } from "./AuthShell";
import { loginSchema, type LoginFormValues } from "./auth-schemas";

export function LoginForm() {
  const params = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    reValidateMode: "onBlur",
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = form;
  const callbackUrl = params.get("callbackUrl") ?? "/home";
  const justRegistered = params.get("registered") === "1";

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
    <form className={authStyles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
      {justRegistered ? (
        <Notice tone="success" role="status">
          Cuenta creada. Ya podés iniciar sesión.
        </Notice>
      ) : null}
      <Field
        label="Correo"
        autoComplete="email"
        type="email"
        disabled={isSubmitting}
        error={errors.email?.message}
        required
        {...register("email")}
      />
      <Field
        label="Contraseña"
        autoComplete="current-password"
        type="password"
        disabled={isSubmitting}
        error={errors.password?.message}
        required
        {...register("password")}
      />
      {formError ? (
        <Notice tone="error" role="alert">
          {formError}
        </Notice>
      ) : null}
      <div className={authStyles.actions}>
        <Button type="submit" variant="primary" size="md" fullWidth disabled={isSubmitting}>
          {isSubmitting ? "Ingresando..." : "Ingresar"}
        </Button>
        <button
          className={authStyles.disabledSocial}
          disabled
          type="button"
          aria-disabled="true"
        >
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

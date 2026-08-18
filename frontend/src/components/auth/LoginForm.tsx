"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Button, Field, Notice } from "@/components/ui";
import {
  isRateLimitedCode,
  isUnavailableCode,
  parseRetryCode,
  parseUnavailableCode,
} from "@/lib/server/auth-rate-limit";
import { authStyles } from "./AuthShell";
import { loginSchema, nowMs, type LoginFormValues } from "./auth-schemas";

const RATE_LIMITED_MESSAGE =
  "Intentá de nuevo en unos minutos. Demasiados intentos desde esta conexión.";
const UNAVAILABLE_MESSAGE =
  "El servicio de inicio de sesión está temporalmente no disponible. Intentá de nuevo en unos minutos.";

export function LoginForm() {
  const params = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);
  const [rateLimitedUntil, setRateLimitedUntil] = useState<number | null>(null);
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

  useEffect(() => {
    if (rateLimitedUntil === null) return;
    const timer = setInterval(() => {
      if (nowMs() >= rateLimitedUntil) {
        setRateLimitedUntil(null);
        setFormError(null);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [rateLimitedUntil]);

  async function onSubmit(values: LoginFormValues) {
    setFormError(null);
    const result = await signIn("credentials", {
      ...values,
      callbackUrl,
      redirect: false,
    });
    if (isRateLimitedCode(result?.code)) {
      // The bounded error code carries the server-clamped retry duration.
      const retryAfterSeconds = parseRetryCode(result.code) ?? 60;
      setRateLimitedUntil(nowMs() + retryAfterSeconds * 1000);
      setFormError(RATE_LIMITED_MESSAGE);
      return;
    }
    if (isUnavailableCode(result?.code)) {
      // Generic temporary-unavailability feedback; never claim a limit was
      // reached. A bounded delay briefly prevents hammering the failing path.
      const retryAfterSeconds = parseUnavailableCode(result.code) ?? 60;
      setRateLimitedUntil(nowMs() + retryAfterSeconds * 1000);
      setFormError(UNAVAILABLE_MESSAGE);
      return;
    }
    if (result?.error) {
      setFormError(
        "No pudimos iniciar sesión con esos datos. Revisalos e intentá otra vez.",
      );
      return;
    }
    window.location.assign(result?.url ?? callbackUrl);
  }

  const blocked = rateLimitedUntil !== null;

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
        disabled={isSubmitting || blocked}
        error={errors.email?.message}
        required
        {...register("email")}
      />
      <Field
        label="Contraseña"
        autoComplete="current-password"
        type="password"
        disabled={isSubmitting || blocked}
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
        <Button
          type="submit"
          variant="primary"
          size="md"
          fullWidth
          disabled={isSubmitting || blocked}
        >
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

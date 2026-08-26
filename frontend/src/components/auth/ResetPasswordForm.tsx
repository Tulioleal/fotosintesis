"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Button, Field, Notice } from "@/components/ui";
import { ApiClientError, apiClient } from "@/lib/api/client";
import { authStyles } from "./AuthShell";
import { nowMs, resetPasswordSchema, type ResetPasswordFormValues } from "./auth-schemas";

const NEUTRAL_RESET_MESSAGE =
  "Si el enlace era válido, tu contraseña ya fue actualizada. Ya podés iniciar sesión con la nueva contraseña.";

export function ResetPasswordForm() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [message, setMessage] = useState<string | null>(null);
  const [rateLimitedUntil, setRateLimitedUntil] = useState<number | null>(null);
  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    reValidateMode: "onBlur",
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = form;

  useEffect(() => {
    if (rateLimitedUntil === null) return;
    const timer = setInterval(() => {
      if (nowMs() >= rateLimitedUntil) {
        setRateLimitedUntil(null);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [rateLimitedUntil]);

  async function onSubmit(values: ResetPasswordFormValues) {
    try {
      await apiClient.confirmRecovery({ token, password: values.password });
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 429) {
        const retryAfterSeconds = error.retryAfterSeconds ?? 60;
        setRateLimitedUntil(nowMs() + retryAfterSeconds * 1000);
      }
    }
    // The backend response is fully neutral, so the completion copy never
    // distinguishes a valid from an invalid, expired, or used token.
    setMessage(NEUTRAL_RESET_MESSAGE);
  }

  const blocked = rateLimitedUntil !== null;

  return (
    <form className={authStyles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
      <Field
        label="Nueva contraseña"
        autoComplete="new-password"
        type="password"
        disabled={isSubmitting || blocked}
        error={errors.password?.message}
        required
        {...register("password")}
      />
      <Field
        label="Confirmar contraseña"
        autoComplete="new-password"
        type="password"
        disabled={isSubmitting || blocked}
        error={errors.confirmPassword?.message}
        required
        {...register("confirmPassword")}
      />
      {message ? (
        <Notice tone="success" role="status">
          {message}
        </Notice>
      ) : null}
      <div className={authStyles.actions}>
        <Button type="submit" variant="primary" size="md" fullWidth disabled={isSubmitting || blocked}>
          {isSubmitting ? "Actualizando..." : "Actualizar contraseña"}
        </Button>
      </div>
      <p className={authStyles.links}>
        <Link href="/login">Volver a ingresar</Link>
        <Link href="/forgot-password">Solicitar un enlace nuevo</Link>
      </p>
    </form>
  );
}

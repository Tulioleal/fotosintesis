"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Button, Field, Notice } from "@/components/ui";
import { ApiClientError, apiClient } from "@/lib/api/client";
import { authStyles } from "./AuthShell";
import { nowMs, recoverySchema, type RecoveryFormValues } from "./auth-schemas";

const NEUTRAL_RECOVERY_MESSAGE =
  "Si el correo existe en Fotosíntesis, vamos a preparar las instrucciones para que vuelvas a entrar.";

export function RecoveryForm() {
  const [message, setMessage] = useState<string | null>(null);
  const [rateLimitedUntil, setRateLimitedUntil] = useState<number | null>(null);
  const form = useForm<RecoveryFormValues>({
    resolver: zodResolver(recoverySchema),
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

  async function onSubmit(values: RecoveryFormValues) {
    try {
      const response = await apiClient.requestRecovery(values);
      setMessage(response.message);
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 429) {
        const retryAfterSeconds = error.retryAfterSeconds ?? 60;
        setRateLimitedUntil(nowMs() + retryAfterSeconds * 1000);
        setMessage(NEUTRAL_RECOVERY_MESSAGE);
        return;
      }
      setMessage(NEUTRAL_RECOVERY_MESSAGE);
    }
  }

  const blocked = rateLimitedUntil !== null;

  return (
    <form className={authStyles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
      <Field
        label="Correo"
        autoComplete="email"
        type="email"
        disabled={isSubmitting || blocked}
        error={errors.email?.message}
        required
        {...register("email")}
      />
      {message ? (
        <Notice tone="success" role="status">
          {message}
        </Notice>
      ) : null}
      <div className={authStyles.actions}>
        <Button type="submit" variant="primary" size="md" fullWidth disabled={isSubmitting || blocked}>
          {isSubmitting ? "Preparando..." : "Recuperar acceso"}
        </Button>
      </div>
      <p className={authStyles.links}>
        <Link href="/login">Volver a ingresar</Link>
      </p>
    </form>
  );
}

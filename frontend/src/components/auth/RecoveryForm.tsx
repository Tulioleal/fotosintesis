"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button, Field, Notice } from "@/components/ui";
import { apiClient } from "@/lib/api/client";
import { authStyles } from "./AuthShell";
import { recoverySchema, type RecoveryFormValues } from "./auth-schemas";

export function RecoveryForm() {
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<RecoveryFormValues>({
    resolver: zodResolver(recoverySchema),
    reValidateMode: "onBlur",
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = form;

  async function onSubmit(values: RecoveryFormValues) {
    const response = await apiClient.requestRecovery(values);
    setMessage(response.message);
  }

  return (
    <form className={authStyles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
      <Field
        label="Correo"
        autoComplete="email"
        type="email"
        disabled={isSubmitting}
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
        <Button type="submit" variant="primary" size="md" fullWidth disabled={isSubmitting}>
          {isSubmitting ? "Preparando..." : "Recuperar acceso"}
        </Button>
      </div>
      <p className={authStyles.links}>
        <Link href="/login">Volver a ingresar</Link>
      </p>
    </form>
  );
}

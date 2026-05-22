"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { apiClient } from "@/lib/generated/client";
import { authStyles } from "./AuthShell";
import { recoverySchema, type RecoveryFormValues } from "./auth-schemas";

export function RecoveryForm() {
  const [message, setMessage] = useState<string | null>(null);
  const form = useForm<RecoveryFormValues>({
    resolver: zodResolver(recoverySchema),
  });

  async function onSubmit(values: RecoveryFormValues) {
    const response = await apiClient.requestRecovery(values);
    setMessage(response.message);
  }

  return (
    <form className={authStyles.form} onSubmit={form.handleSubmit(onSubmit)}>
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
      {message && <p>{message}</p>}
      <button
        className={authStyles.primary}
        disabled={form.formState.isSubmitting}
        type="submit"
      >
        {form.formState.isSubmitting ? "Preparando..." : "Recuperar acceso"}
      </button>
      <p className={authStyles.links}>
        <Link href="/login">Volver a ingresar</Link>
      </p>
    </form>
  );
}

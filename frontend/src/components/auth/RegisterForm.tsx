"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button, Field, Notice } from "@/components/ui";
import { apiClient } from "@/lib/api/client";
import { authStyles } from "./AuthShell";
import { registerSchema, type RegisterFormValues } from "./auth-schemas";

export function RegisterForm() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    reValidateMode: "onBlur",
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = form;

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
    <form
      className={authStyles.form}
      onSubmit={handleSubmit(onSubmit)}
      noValidate
    >
      <Field
        label="Nombre"
        autoComplete="name"
        disabled={isSubmitting}
        error={errors.name?.message}
        required
        {...register("name")}
      />
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
        autoComplete="new-password"
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
        <Button
          type="submit"
          variant="primary"
          size="md"
          fullWidth
          disabled={isSubmitting}
        >
          {isSubmitting ? "Creando cuenta..." : "Crear cuenta"}
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
        <Link href="/login">Ya tengo cuenta</Link>
      </p>
    </form>
  );
}

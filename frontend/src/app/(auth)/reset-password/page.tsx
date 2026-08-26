import { Suspense } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";

export default function ResetPasswordPage() {
  return (
    <AuthShell
      title="Crear una contraseña nueva"
      description="Definí una contraseña nueva para recuperar el acceso a tu cuenta."
    >
      <Suspense fallback={<p>Cargando formulario...</p>}>
        <ResetPasswordForm />
      </Suspense>
    </AuthShell>
  );
}

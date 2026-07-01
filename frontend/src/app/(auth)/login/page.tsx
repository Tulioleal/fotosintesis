import { Suspense } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <AuthShell
      title="Ingresá a tu cuenta"
      description="Usá tu correo y contraseña para retomar el cuidado de tu jardín."
    >
      <Suspense fallback={<p>Cargando formulario...</p>}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}

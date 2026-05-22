import { Suspense } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <AuthShell
      title="Ingresá a Fotosíntesis"
      description="Usá tu correo y contraseña. Si algo falla, te vamos a mostrar un mensaje recuperable."
    >
      <Suspense fallback={<p>Cargando formulario...</p>}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}

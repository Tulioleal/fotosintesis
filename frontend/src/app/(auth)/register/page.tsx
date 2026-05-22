import { AuthShell } from "@/components/auth/AuthShell";
import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <AuthShell
      title="Creá tu cuenta"
      description="Guardamos tu acceso con contraseña segura y dejamos la verificación de correo preparada para más adelante."
    >
      <RegisterForm />
    </AuthShell>
  );
}

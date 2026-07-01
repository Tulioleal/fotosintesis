import { AuthShell } from "@/components/auth/AuthShell";
import { RegisterForm } from "@/components/auth/RegisterForm";

export default function RegisterPage() {
  return (
    <AuthShell
      title="Creá tu cuenta"
      description="Empezá a identificar y organizar tus plantas con una contraseña segura."
    >
      <RegisterForm />
    </AuthShell>
  );
}

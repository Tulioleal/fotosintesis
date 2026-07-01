import { AuthShell } from "@/components/auth/AuthShell";
import { RecoveryForm } from "@/components/auth/RecoveryForm";

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      title="Recuperar acceso"
      description="Si el correo existe en Fotosíntesis, vamos a preparar las instrucciones para que vuelvas a entrar. El envío del email queda para una integración posterior."
    >
      <RecoveryForm />
    </AuthShell>
  );
}

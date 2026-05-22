import { AuthShell } from "@/components/auth/AuthShell";
import { RecoveryForm } from "@/components/auth/RecoveryForm";

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      title="Recuperar acceso"
      description="Si el correo existe, vamos a preparar las instrucciones para recuperar la cuenta. El envío de email queda para una integración posterior."
    >
      <RecoveryForm />
    </AuthShell>
  );
}

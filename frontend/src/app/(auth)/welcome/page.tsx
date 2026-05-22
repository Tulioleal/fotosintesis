import Link from "next/link";
import { AuthShell, authStyles } from "@/components/auth/AuthShell";

export default function WelcomePage() {
  return (
    <AuthShell
      title="Tu jardín empieza acá"
      description="Identificá plantas, organizá cuidados y prepará tu espacio para el asistente botánico."
    >
      <div className={authStyles.actions}>
        <Link className={authStyles.primary} href="/register">
          Crear cuenta
        </Link>
        <Link className={authStyles.secondary} href="/login">
          Ingresar
        </Link>
      </div>
    </AuthShell>
  );
}

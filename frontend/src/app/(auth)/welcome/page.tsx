import Link from "next/link";
import { LeafIcon } from "@phosphor-icons/react/ssr";
import { AuthShell, authStyles } from "@/components/auth/AuthShell";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./page.module.scss";

export default function WelcomePage() {
  return (
    <div className={styles.wrapper}>
      <section className={styles.hero} aria-label="Resumen de Fotosíntesis">
        <span className={styles.heroIcon} aria-hidden="true">
          <LeafIcon aria-hidden="true" weight="fill" size="1.5rem" className={iconStyles.toneOnPrimary} />
        </span>
        <h2 className={styles.heroTitle}>Un jardín con criterio botánico</h2>
        <p className={styles.heroCopy}>
          Identificá especies, organizá tus plantas y prepará el terreno para el
          asistente con fuentes verificadas.
        </p>
      </section>
      <AuthShell
        title="Tu jardín empieza acá"
        description="Elegí cómo querés entrar: crear una cuenta nueva o ingresar si ya la tenés."
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
    </div>
  );
}

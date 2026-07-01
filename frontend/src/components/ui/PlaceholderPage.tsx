import Link from "next/link";
import { LeafIcon } from "@phosphor-icons/react/ssr";
import { Card, PageHeader } from "@/components/ui";
import iconStyles from "./Icons.module.scss";
import styles from "./PlaceholderPage.module.scss";

export function PlaceholderPage({
  title,
  description = "Este acceso ya está protegido y navegable, pero la lógica real queda fuera de este slice.",
}: Readonly<{ title: string; description?: string }>) {
  return (
    <>
      <PageHeader
        eyebrow="Próximamente"
        heading={title}
        description={description}
        art={
          <LeafIcon
            aria-hidden="true"
            weight="fill"
            size="2rem"
            className={iconStyles.tonePrimary}
          />
        }
      />
      <Card variant="tonal" padding="md" className={styles.panel}>
        <p className={styles.copy}>
          Esta pantalla forma parte de la base navegable. La lógica real se
          integrará en próximas iteraciones.
        </p>
        <Link className={styles.link} href="/home">
          Volver al Home
        </Link>
      </Card>
    </>
  );
}

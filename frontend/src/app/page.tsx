import {
  ArrowRightIcon,
  BellIcon,
  CameraIcon,
  EnvelopeSimpleIcon,
  GlobeHemisphereWestIcon,
  UserCircleIcon,
} from "@phosphor-icons/react/ssr";
import { AppLink } from "@/components/ui";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./page.module.scss";
import Image from "next/image";

const heroImage: { src?: string; alt: string } = {
  src: "/references/bienvenida-con-funcionalidades/hero-plant-identification.png",
  alt: "Hojas tropicales iluminadas por luz natural en un ambiente botánico moderno",
};

type FeatureTone = "primary" | "secondary" | "tertiary";
type FeatureSize = "wide" | "compact" | "full";

type FeatureCard = {
  title: string;
  description: string;
  image?: string;
  tone: FeatureTone;
  size: FeatureSize;
};

const featureCards: FeatureCard[] = [
  {
    title: "Identificación instantánea",
    description: "Reconocé especies con una foto y resultados trazables.",
    image:
      "/references/bienvenida-con-funcionalidades/feature-identificacion-instantanea.png",
    tone: "primary",
    size: "wide",
  },
  {
    title: "Guías de cuidado",
    description: "Consejos personalizados sobre riego, luz y seguimiento.",
    image:
      "/references/bienvenida-con-funcionalidades/feature-guias-cuidado.png",
    tone: "secondary",
    size: "compact",
  },
  {
    title: "Recordatorios inteligentes",
    description: "Organizá tareas de cuidado y mantené tu jardín al día.",
    image:
      "/references/bienvenida-con-funcionalidades/feature-recordatorios-inteligentes.png",
    tone: "tertiary",
    size: "full",
  },
];

const toneClass: Record<FeatureTone, string> = {
  primary: styles.tonePrimary,
  secondary: styles.toneSecondary,
  tertiary: styles.toneTertiary,
};

const sizeClass: Record<FeatureSize, string> = {
  wide: styles.sizeWide,
  compact: styles.sizeCompact,
  full: styles.sizeFull,
};

const overlayClass: Record<FeatureTone, string> = {
  primary: styles.overlayPrimary,
  secondary: styles.overlaySecondary,
  tertiary: styles.overlayTertiary,
};

export default function Home() {
  return (
    <div className={styles.page}>
      <a className={styles.skipLink} href="#main-content">
        Saltar al contenido
      </a>
      <header className={styles.topBar}>
        <div className={styles.topBarInner}>
          <AppLink className={styles.brand} href="/" variant="plain">
            Fotosíntesis
          </AppLink>
          <div className={styles.topBarActions}>
            <button
              type="button"
              className={styles.iconButton}
              aria-label="Notificaciones"
            >
              <BellIcon
                aria-hidden="true"
                weight="regular"
                size="1.25rem"
                className={iconStyles.toneOnSurfaceVariant}
              />
            </button>
            <button
              type="button"
              className={styles.iconButton}
              aria-label="Cuenta"
            >
              <UserCircleIcon
                aria-hidden="true"
                weight="regular"
                size="1.25rem"
                className={iconStyles.toneOnSurfaceVariant}
              />
            </button>
          </div>
        </div>
      </header>

      <main id="main-content" className={styles.main} tabIndex={-1}>
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <div className={styles.heroCopy}>
              <h1 className={styles.heroTitle}>
                Tu asistente personal para el cuidado de plantas.
              </h1>
              <p className={styles.heroBody}>
                Registrá, monitoreá y recibí consejos estructurados para
                mantener tu jardín saludable. Una herencia botánica digital
                diseñada para la vida moderna.
              </p>
              <div className={styles.heroActions}>
                <AppLink
                  className={styles.primaryCta}
                  href="/login"
                  variant="plain"
                  trailingIcon={
                    <ArrowRightIcon
                      aria-hidden="true"
                      weight="bold"
                      size="1.1rem"
                      className={iconStyles.toneOnPrimary}
                    />
                  }
                >
                  Iniciar sesión
                </AppLink>
                <AppLink
                  className={styles.secondaryCta}
                  href="/register"
                  variant="plain"
                >
                  Registrarse
                </AppLink>
              </div>
            </div>

            <div className={styles.heroVisual} aria-hidden="true">
              <div className={styles.heroVisualGlow} />
              {heroImage.src ? (
                <Image
                  className={styles.heroImage}
                  src={heroImage.src}
                  alt={heroImage.alt}
                  layout="fill"
                />
              ) : (
                <div className={styles.heroImageFallback} />
              )}
              <div className={styles.heroFloat}>
                <span className={styles.heroFloatIcon}>
                  <CameraIcon
                    aria-hidden="true"
                    weight="light"
                    size="1.5rem"
                    className={iconStyles.toneOnPrimary}
                  />
                </span>
                <div className={styles.heroFloatCopy}>
                  <p className={styles.heroFloatTitle}>
                    Identificación instantánea
                  </p>
                  <p className={styles.heroFloatSubtitle}>
                    Descubrí especies con una foto
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          className={styles.features}
          aria-label="Funcionalidades de Fotosíntesis"
        >
          <div className={styles.featuresInner}>
            <header className={styles.featuresHeader}>
              <h2 className={styles.featuresTitle}>
                Todo lo que necesitás para un jardín vibrante
              </h2>
            </header>
            <div className={styles.featuresGrid}>
              {featureCards.map((card) => (
                <article
                  key={card.title}
                  className={`${styles.featureCard} ${toneClass[card.tone]} ${sizeClass[card.size]}`}
                >
                  {card.image ? (
                    <Image
                      className={styles.featureImage}
                      src={card.image}
                      alt=""
                      loading="lazy"
                      layout="fill"
                    />
                  ) : (
                    <div
                      className={styles.featureFallback}
                      aria-hidden="true"
                    />
                  )}
                  <div
                    className={`${styles.featureOverlay} ${overlayClass[card.tone]}`}
                  />
                  <div className={styles.featureContent}>
                    <h3 className={styles.featureTitle}>{card.title}</h3>
                    <p className={styles.featureDescription}>
                      {card.description}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerBrandGroup}>
            <span className={styles.footerBrand}>Fotosíntesis</span>
            <span className={styles.footerCopy}>
              © {new Date().getFullYear()} Fotosíntesis. Cuidado botánico
              trazable.
            </span>
          </div>
          <nav
            className={styles.footerLinks}
            aria-label="Enlaces secundarios del pie"
          >
            <AppLink
              className={styles.footerLink}
              href="/welcome"
              variant="footer"
            >
              Cómo funciona
            </AppLink>
            <AppLink
              className={styles.footerLink}
              href="/login"
              variant="footer"
            >
              Ingresar
            </AppLink>
            <AppLink
              className={styles.footerLink}
              href="/register"
              variant="footer"
            >
              Crear cuenta
            </AppLink>
          </nav>
          <div className={styles.footerIcons} aria-hidden="true">
            <GlobeHemisphereWestIcon
              aria-hidden="true"
              weight="regular"
              size="1.25rem"
              className={iconStyles.tonePrimary}
            />
            <EnvelopeSimpleIcon
              aria-hidden="true"
              weight="regular"
              size="1.25rem"
              className={iconStyles.tonePrimary}
            />
          </div>
        </div>
      </footer>
    </div>
  );
}

import styles from "./page.module.scss";

export default function Home() {
  return (
    <main className={styles.main}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Fotosintesis AI</p>
        <h1>Cuida tus plantas con asistencia botanica trazable.</h1>
        <p>
          Base del MVP lista para integrar identificacion visual, Mi Jardin,
          recordatorios, medidor de luz y asistente con RAG.
        </p>
      </section>
    </main>
  );
}

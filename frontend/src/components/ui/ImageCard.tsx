"use client";

import { type ReactNode } from "react";
import styles from "./ImageCard.module.scss";

export type ImageCardVariant = "default" | "result" | "overlay";

export interface ImageCardProps {
  image?: ReactNode;
  imageAlt?: string;
  caption?: ReactNode;
  eyebrow?: ReactNode;
  title?: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  fallback?: ReactNode;
  variant?: ImageCardVariant;
  children?: ReactNode;
  className?: string;
}

export function ImageCard({
  image,
  imageAlt = "",
  caption,
  eyebrow,
  title,
  description,
  meta,
  fallback,
  variant = "default",
  children,
  className,
}: ImageCardProps) {
  const classes = [styles.card, styles[`variant-${variant}`], className]
    .filter(Boolean)
    .join(" ");

  if (variant === "overlay") {
    return (
      <article className={classes}>
        {image ? (
          <div className={styles.overlayImage} role="img" aria-label={imageAlt}>
            {image}
          </div>
        ) : (
          <div className={styles.fallback} aria-hidden="true">
            {fallback ?? <span className={styles.fallbackLeaf} />}
          </div>
        )}
        <div className={styles.overlay} aria-hidden="true" />
        <div className={styles.overlayBody}>
          {eyebrow ? <p className={styles.overlayEyebrow}>{eyebrow}</p> : null}
          {title ? <h3 className={styles.overlayTitle}>{title}</h3> : null}
          {description ? (
            <p className={styles.overlayCopy}>{description}</p>
          ) : null}
          {meta ? <div className={styles.meta}>{meta}</div> : null}
          {children}
        </div>
      </article>
    );
  }

  return (
    <article className={classes}>
      <div className={styles.frame}>
        {image ? (
          <div className={styles.image}>{image}</div>
        ) : (
          <div className={styles.fallback} aria-hidden="true">
            {fallback ?? <span className={styles.fallbackLeaf} />}
          </div>
        )}
        {caption ? (
          <figcaption className={styles.caption}>{caption}</figcaption>
        ) : null}
      </div>
      <div className={styles.body}>
        {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
        {title ? <h3 className={styles.title}>{title}</h3> : null}
        {description ? (
          <p className={styles.description}>{description}</p>
        ) : null}
        {meta && (
          <hr
            style={{
              width: "100%",
              border: "none",
              height: "1px",
              backgroundColor: "#eee",
            }}
          />
        )}
        {meta ? <div className={styles.meta}>{meta}</div> : null}
        {children}
      </div>
    </article>
  );
}

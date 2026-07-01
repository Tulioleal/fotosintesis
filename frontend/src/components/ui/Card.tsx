import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import styles from "./Card.module.scss";

export type CardVariant =
  | "tonal"
  | "outlined"
  | "quiet"
  | "elevated"
  | "callout";

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "article" | "section" | "div";
  variant?: CardVariant;
  padding?: "sm" | "md" | "lg";
  eyebrow?: ReactNode;
  heading?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  art?: ReactNode;
  children?: ReactNode;
}

export const Card = forwardRef<HTMLElement, CardProps>(function Card(
  {
    as: Tag = "article",
    variant = "tonal",
    padding = "md",
    eyebrow,
    heading,
    description,
    actions,
    art,
    className,
    children,
    ...rest
  },
  ref,
) {
  const classes = [
    styles.card,
    styles[`variant-${variant}`],
    styles[`padding-${padding}`],
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Tag ref={ref as never} className={classes} {...rest}>
      {art ? (
        <div className={styles.art} aria-hidden="true">
          {art}
        </div>
      ) : null}
      <div className={styles.body}>
        {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
        {heading ? <h3 className={styles.title}>{heading}</h3> : null}
        {description ? (
          <p className={styles.description}>{description}</p>
        ) : null}
        {children ? <div className={styles.content}>{children}</div> : null}
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>
    </Tag>
  );
});

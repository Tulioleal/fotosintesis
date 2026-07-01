import { type HTMLAttributes, type ReactNode } from "react";
import styles from "./PageHeader.module.scss";

export interface PageHeaderProps extends HTMLAttributes<HTMLElement> {
  eyebrow?: ReactNode;
  heading: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  art?: ReactNode;
  bordered?: boolean;
}

export function PageHeader({
  eyebrow,
  heading,
  description,
  actions,
  art,
  bordered = false,
  className,
  ...rest
}: PageHeaderProps) {
  const classes = [
    styles.header,
    bordered ? styles.bordered : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <header className={classes} {...rest}>
      <div className={styles.text}>
        {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
        <h1 className={styles.title}>{heading}</h1>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {art ? (
        <div className={styles.art} aria-hidden="true">
          {art}
        </div>
      ) : null}
      {actions ? <div className={styles.actions}>{actions}</div> : null}
    </header>
  );
}

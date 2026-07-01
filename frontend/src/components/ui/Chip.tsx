import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import styles from "./Chip.module.scss";

export type ChipTone = "neutral" | "primary" | "secondary" | "success" | "warning" | "error";

export interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: ChipTone;
  icon?: ReactNode;
  children: ReactNode;
}

const toneToLabel: Record<ChipTone, string> = {
  neutral: "Etiqueta",
  primary: "Etiqueta",
  secondary: "Etiqueta",
  success: "Estado",
  warning: "Estado",
  error: "Estado",
};

export const Chip = forwardRef<HTMLSpanElement, ChipProps>(function Chip(
  { tone = "neutral", icon, className, children, ...rest },
  ref,
) {
  const classes = [styles.chip, styles[`tone-${tone}`], className].filter(Boolean).join(" ");

  return (
    <span ref={ref} className={classes} {...rest}>
      {icon ? (
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <span className={styles.label}>{children}</span>
    </span>
  );
});

export function describeChip(tone: ChipTone, label: string) {
  return `${toneToLabel[tone]}: ${label}`;
}

"use client";

import {
  forwardRef,
  type ButtonHTMLAttributes,
  type ElementType,
  type ReactNode,
} from "react";
import { buildButtonClassNames } from "./buttonClasses";
import styles from "./Button.module.scss";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "tertiary"
  | "outline"
  | "ghost"
  | "destructive";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  as?: ElementType;
  href?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  type?: "button" | "submit" | "reset";
  children: ReactNode;
}

export const Button = forwardRef<HTMLElement, ButtonProps>(function Button(
  {
    as,
    href,
    variant = "primary",
    size = "md",
    fullWidth = false,
    leadingIcon,
    trailingIcon,
    className,
    children,
    type,
    ...rest
  },
  ref,
) {
  const classes = buildButtonClassNames(variant, size, fullWidth, className);
  const Component: ElementType = as ?? "button";
  const isNativeButton = Component === "button";
  const buttonType = isNativeButton ? type ?? "button" : undefined;

  return (
    <Component
      ref={ref as never}
      className={classes}
      href={href}
      type={buttonType}
      {...rest}
    >
      {leadingIcon ? (
        <span className={styles.icon} aria-hidden="true">
          {leadingIcon}
        </span>
      ) : null}
      <span className={styles.label}>{children}</span>
      {trailingIcon ? (
        <span className={styles.icon} aria-hidden="true">
          {trailingIcon}
        </span>
      ) : null}
    </Component>
  );
});

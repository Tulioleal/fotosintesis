import NextLink from "next/link";
import {
  forwardRef,
  type AnchorHTMLAttributes,
  type ReactNode,
} from "react";
import type { ButtonSize, ButtonVariant } from "./Button";
import { buildButtonClassNames } from "./buttonClasses";
import styles from "./AppLink.module.scss";

export type AppLinkVariant =
  | "default"
  | "subtle"
  | "nav"
  | "footer"
  | "back"
  | "plain"
  | "button";

export interface AppLinkProps
  extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  href: string;
  external?: boolean;
  variant?: AppLinkVariant;
  buttonVariant?: ButtonVariant;
  buttonSize?: ButtonSize;
  fullWidth?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  children: ReactNode;
}

function isExternalHref(href: string): boolean {
  return /^(https?:)?\/\//i.test(href) || /^mailto:/i.test(href) || href.startsWith("tel:");
}

export const AppLink = forwardRef<HTMLAnchorElement, AppLinkProps>(function AppLink(
  {
    href,
    external = false,
    variant = "default",
    buttonVariant = "primary",
    buttonSize = "md",
    fullWidth = false,
    leadingIcon,
    trailingIcon,
    className,
    children,
    ...rest
  },
  ref,
) {
  const linkClasses = buildLinkClassNames({
    variant,
    buttonVariant,
    buttonSize,
    fullWidth,
    className,
  });

  const content = (
    <>
      {leadingIcon ? (
        <span className={styles.leading} aria-hidden="true">
          {leadingIcon}
        </span>
      ) : null}
      <span className={styles.label ?? undefined}>{children}</span>
      {trailingIcon ? (
        <span className={styles.trailing} aria-hidden="true">
          {trailingIcon}
        </span>
      ) : null}
    </>
  );

  const isExternal = external || isExternalHref(href);

  if (isExternal) {
    return (
      <a
        ref={ref}
        className={linkClasses}
        href={href}
        target="_blank"
        rel="noreferrer"
        {...rest}
      >
        {content}
      </a>
    );
  }

  return (
    <NextLink ref={ref} className={linkClasses} href={href} {...rest}>
      {content}
    </NextLink>
  );
});

function buildLinkClassNames({
  variant,
  buttonVariant,
  buttonSize,
  fullWidth,
  className,
}: {
  variant: AppLinkVariant;
  buttonVariant: ButtonVariant;
  buttonSize: ButtonSize;
  fullWidth: boolean;
  className?: string;
}): string {
  const parts: Array<string | null | undefined> = [
    styles.link,
    styles[`variant-${variant}`],
  ];

  if (variant === "button") {
    parts.push(
      buildButtonClassNames(buttonVariant, buttonSize, fullWidth, undefined),
    );
  } else if (fullWidth) {
    parts.push(styles.fullWidth);
  }

  parts.push(className);
  return parts.filter(Boolean).join(" ");
}

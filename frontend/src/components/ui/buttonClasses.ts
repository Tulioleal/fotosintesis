import type { ButtonSize, ButtonVariant } from "./Button";
import buttonStyles from "./Button.module.scss";

export function buildButtonClassNames(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  fullWidth = false,
  extra?: string,
): string {
  return [
    buttonStyles.button,
    buttonStyles[`variant-${variant}`],
    buttonStyles[`size-${size}`],
    fullWidth ? buttonStyles.fullWidth : null,
    extra,
  ]
    .filter(Boolean)
    .join(" ");
}

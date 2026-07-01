import { forwardRef, type HTMLAttributes, type ReactNode } from "react";
import styles from "./Notice.module.scss";

export type NoticeTone = "info" | "success" | "warning" | "error";

export interface NoticeProps extends HTMLAttributes<HTMLDivElement> {
  tone?: NoticeTone;
  heading?: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
}

const toneToRole: Record<NoticeTone, "status" | "alert"> = {
  info: "status",
  success: "status",
  warning: "status",
  error: "alert",
};

export const Notice = forwardRef<HTMLDivElement, NoticeProps>(function Notice(
  { tone = "info", heading, icon, className, children, ...rest },
  ref,
) {
  const classes = [styles.notice, styles[`tone-${tone}`], className].filter(Boolean).join(" ");

  return (
    <div ref={ref} className={classes} role={toneToRole[tone]} {...rest}>
      {icon ? (
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <div className={styles.body}>
        {heading ? <p className={styles.title}>{heading}</p> : null}
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
});

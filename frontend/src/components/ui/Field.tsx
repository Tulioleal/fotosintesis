import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useId,
} from "react";
import styles from "./Field.module.scss";

export interface FieldBaseProps {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  optionalLabel?: string;
}

export interface FieldProps
  extends FieldBaseProps,
    Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  kind?: "input";
}

export interface TextareaFieldProps
  extends FieldBaseProps,
    TextareaHTMLAttributes<HTMLTextAreaElement> {
  kind: "textarea";
}

export interface SelectFieldProps
  extends FieldBaseProps,
    SelectHTMLAttributes<HTMLSelectElement> {
  kind: "select";
  children: ReactNode;
}

export type AnyFieldProps = FieldProps | TextareaFieldProps | SelectFieldProps;

function describeError(errorId: string, hintId: string, error?: ReactNode) {
  if (error) return { "aria-invalid": true, "aria-errormessage": errorId };
  if (hintId) return { "aria-describedby": hintId };
  return {};
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, hint, error, required, optionalLabel, id, className, ...rest },
  ref,
) {
  const reactId = useId();
  const inputId = id ?? `field-${reactId}`;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const inputClasses = [styles.input, error ? styles.invalid : null, className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId} data-required={required || undefined}>
        <span>{label}</span>
        {optionalLabel ? <span className={styles.optional}>{optionalLabel}</span> : null}
      </label>
      {hint && !error ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
      <input
        ref={ref}
        id={inputId}
        className={inputClasses}
        required={required}
        {...describeError(errorId ?? "", hintId ?? "", error)}
        {...rest}
      />
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
});

export const TextareaField = forwardRef<HTMLTextAreaElement, TextareaFieldProps>(
  function TextareaField(
    { label, hint, error, required, optionalLabel, id, className, ...rest },
    ref,
  ) {
    const reactId = useId();
    const inputId = id ?? `textarea-${reactId}`;
    const hintId = hint ? `${inputId}-hint` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;
    const inputClasses = [
      styles.input,
      styles.textarea,
      error ? styles.invalid : null,
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <div className={styles.field}>
        <label className={styles.label} htmlFor={inputId} data-required={required || undefined}>
          <span>{label}</span>
          {optionalLabel ? <span className={styles.optional}>{optionalLabel}</span> : null}
        </label>
        {hint && !error ? (
          <p id={hintId} className={styles.hint}>
            {hint}
          </p>
        ) : null}
        <textarea
          ref={ref}
          id={inputId}
          className={inputClasses}
          required={required}
          {...describeError(errorId ?? "", hintId ?? "", error)}
          {...rest}
        />
        {error ? (
          <p id={errorId} className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, hint, error, required, optionalLabel, id, className, children, ...rest },
  ref,
) {
  const reactId = useId();
  const inputId = id ?? `select-${reactId}`;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const inputClasses = [
    styles.input,
    styles.select,
    error ? styles.invalid : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId} data-required={required || undefined}>
        <span>{label}</span>
        {optionalLabel ? <span className={styles.optional}>{optionalLabel}</span> : null}
      </label>
      {hint && !error ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
      <select
        ref={ref}
        id={inputId}
        className={inputClasses}
        required={required}
        {...describeError(errorId ?? "", hintId ?? "", error)}
        {...rest}
      >
        {children}
      </select>
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
});

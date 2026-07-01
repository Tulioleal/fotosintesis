"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  apiClient,
  type AssistantMessage,
  type AssistantReminderSuggestion,
  type AssistantRetryableError,
  type AssistantSource,
  type ReminderCreate,
} from "@/lib/api/client";
import { normalizeReminderAction } from "@/components/reminders/RemindersManager";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import {
  ArrowLeftIcon,
  ArrowUpIcon,
  BrainIcon,
  ImageIcon,
  LeafIcon,
  MapPinIcon,
  UserIcon,
} from "@phosphor-icons/react";
import iconStyles from "@/components/ui/Icons.module.scss";
import styles from "./AssistantChat.module.scss";

type AssistantMessageContentFormat = NonNullable<
  AssistantMessage["content_format"]
>;

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  contentFormat?: AssistantMessageContentFormat | null;
  reminderSuggestion?: AssistantReminderSuggestion | null;
  suggestionStatus?: "accepted" | "error";
};

const recurrenceLabels: Record<ReminderCreate["recurrence"], string> = {
  none: "Unico",
  daily: "Diario",
  weekly: "Semanal",
  monthly: "Mensual",
};

export function AssistantChat() {
  const searchParams = useSearchParams();
  const plant = searchParams.get("plant");
  const binomial = searchParams.get("binomial");
  const scientific = searchParams.get("scientific");
  const hasPlantContext = Boolean(plant);
  const scientificLabel = binomial ?? scientific ?? null;
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<AssistantSource[]>([]);
  const [message, setMessage] = useState(
    plant ? `Tengo una consulta sobre ${plant}: ` : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [acceptingSuggestion, setAcceptingSuggestion] = useState<number | null>(
    null,
  );

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || pending) return;
    setPending(true);
    setError(null);
    setSources([]);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    setMessage("");
    try {
      const response = await apiClient.sendAssistantMessage({
        message: trimmed,
        conversation_id: conversationId,
        plant,
        plant_binomial_name: binomial,
        plant_scientific_name: scientific,
      });
      if (
        "retryable" in response &&
        (response as AssistantRetryableError).retryable
      ) {
        const retryableError = response as AssistantRetryableError;
        if (retryableError.conversation_id) {
          setConversationId(retryableError.conversation_id);
        }
        setError(
          retryableError.detail ||
            "No se pudo generar una respuesta. Intenta de nuevo.",
        );
        return;
      }
      const chatResponse =
        response as import("@/lib/api/client").AssistantChatResponse;
      setConversationId(chatResponse.conversation_id);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: chatResponse.message.content,
          contentFormat: chatResponse.message.content_format,
          reminderSuggestion: chatResponse.reminder_suggestion,
        },
      ]);
      setSources(chatResponse.sources);
    } catch (caught) {
      const detail =
        caught instanceof Error
          ? caught.message
          : "No pudimos contactar al asistente.";
      setError(detail);
    } finally {
      setPending(false);
    }
  }

  async function acceptReminderSuggestion(
    suggestion: AssistantReminderSuggestion,
    messageIndex: number,
  ) {
    if (acceptingSuggestion !== null) return;
    setAcceptingSuggestion(messageIndex);
    setError(null);
    try {
      await apiClient.createReminder({
        garden_plant_id: suggestion.garden_plant_id,
        action: normalizeReminderAction(suggestion.action),
        date: suggestion.due_at.slice(0, 10),
        time: suggestion.due_at.slice(11, 16),
        recurrence: suggestion.recurrence,
        suggestion_justification: suggestion.suggestion_justification,
      });
      setMessages((current) =>
        current.map((item, index) =>
          index === messageIndex
            ? { ...item, suggestionStatus: "accepted" }
            : item,
        ),
      );
    } catch (caught) {
      const detail =
        caught instanceof Error
          ? caught.message
          : "No pudimos crear el recordatorio sugerido.";
      setError(detail);
      setMessages((current) =>
        current.map((item, index) =>
          index === messageIndex
            ? { ...item, suggestionStatus: "error" }
            : item,
        ),
      );
    } finally {
      setAcceptingSuggestion(null);
    }
  }

  return (
    <section
      className={styles.assistant}
      aria-label="Asistente de Fotosintesis"
    >
      <div
        className={`${styles.workspace} ${hasPlantContext ? styles.workspaceWithSidebar : styles.workspaceFull}`}
      >
        {hasPlantContext ? (
          <aside className={styles.sidebar} aria-label="Contexto de la planta">
            <Button
              variant="ghost"
              size="sm"
              className={styles.sidebarBack}
              type="button"
              leadingIcon={
                <ArrowLeftIcon
                  aria-hidden="true"
                  size="1.25rem"
                  weight="regular"
                  className={iconStyles.toneOnSurfaceVariant}
                />
              }
              onClick={() => {
                if (typeof window !== "undefined") {
                  window.history.back();
                }
              }}
            >
              Volver al detalle
            </Button>
            <div className={styles.plantImage} aria-hidden="true">
              <ImageIcon
                aria-hidden="true"
                size="2rem"
                className={iconStyles.toneMuted}
              />
            </div>
            <div className={styles.plantDetails}>
              <div className={styles.plantField}>
                <span className={styles.fieldLabel}>Apodo</span>
                <h2 className={styles.plantName}>{plant}</h2>
              </div>
              {scientificLabel ? (
                <div className={styles.plantField}>
                  <span className={styles.fieldLabel}>Nombre cientifico</span>
                  <p className={styles.plantScientific}>{scientificLabel}</p>
                </div>
              ) : null}
              <div className={styles.plantField}>
                <span className={styles.fieldLabel}>Ubicacion</span>
                <p className={styles.plantPlaceholder}>
                  <MapPinIcon
                    aria-hidden="true"
                    size="1rem"
                    className={iconStyles.toneOnSurfaceVariant}
                  />
                  <span>Sin ubicacion asignada</span>
                </p>
              </div>
              <div className={styles.plantField}>
                <span className={styles.fieldLabel}>Notas del usuario</span>
                <p className={`${styles.plantPlaceholder} ${styles.italic}`}>
                  Anade notas sobre el riego o fertilizacion aqui...
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="md"
              fullWidth
              className={styles.sidebarAction}
              type="button"
              leadingIcon={
                <LeafIcon
                  aria-hidden="true"
                  size="1rem"
                  className={iconStyles.tonePrimary}
                />
              }
              onClick={() => {
                if (typeof window !== "undefined") {
                  window.location.href = "/garden";
                }
              }}
            >
              Ver ficha completa
            </Button>
          </aside>
        ) : null}

        <div className={styles.chatArea}>
          <div className={styles.thread} aria-live="polite">
            {!messages.length ? (
              <p className={styles.empty}>
                Hace una pregunta de cuidado, luz, plagas o recordatorios.
              </p>
            ) : null}
            {messages.map((item, index) => (
              <div
                className={`${styles.messageGroup} ${item.role === "user" ? styles.userGroup : styles.assistantGroup}`}
                key={`${item.role}-${index}`}
              >
                <div className={styles.messageRow}>
                  <span
                    className={`${styles.avatar} ${item.role === "user" ? styles.userAvatar : styles.assistantAvatar}`}
                    aria-hidden="true"
                  >
                    {item.role === "user" ? (
                      <UserIcon
                        aria-hidden="true"
                        size="1.25rem"
                        className={iconStyles.toneOnPrimary}
                      />
                    ) : (
                      <BrainIcon
                        aria-hidden="true"
                        size="1.25rem"
                        className={iconStyles.toneOnPrimary}
                      />
                    )}
                  </span>
                  <div className={styles.messageCol}>
                    <span className={styles.messageLabel}>
                      {item.role === "user" ? "Tu" : "Asistente AI"}
                    </span>
                    <article
                      className={`${styles.message} ${item.role === "user" ? styles.userMessage : styles.assistantMessage}`}
                    >
                      {item.role === "assistant" ? (
                        <AssistantMessageContent
                          content={item.content}
                          contentFormat={item.contentFormat}
                        />
                      ) : (
                        <span className={styles.messageContent}>
                          {item.content}
                        </span>
                      )}
                    </article>
                  </div>
                </div>
                {item.reminderSuggestion ? (
                  <Card
                    variant="callout"
                    className={styles.suggestionCard}
                    eyebrow="Recordatorio sugerido"
                    heading={normalizeReminderAction(
                      item.reminderSuggestion.action,
                    )}
                    description={
                      <>
                        {item.reminderSuggestion.plant_name} &middot;{" "}
                        {formatDateTime(item.reminderSuggestion.due_at)}{" "}
                        &middot;{" "}
                        {recurrenceLabels[item.reminderSuggestion.recurrence]}
                      </>
                    }
                    actions={
                      <Button
                        type="button"
                        size="sm"
                        variant="primary"
                        onClick={() =>
                          acceptReminderSuggestion(
                            item.reminderSuggestion!,
                            index,
                          )
                        }
                        disabled={
                          acceptingSuggestion !== null ||
                          item.suggestionStatus === "accepted"
                        }
                      >
                        {item.suggestionStatus === "accepted"
                          ? "Recordatorio creado"
                          : acceptingSuggestion === index
                            ? "Creando..."
                            : "Aceptar sugerencia"}
                      </Button>
                    }
                  >
                    <p className={styles.suggestionJustification}>
                      {item.reminderSuggestion.suggestion_justification}
                    </p>
                    {item.suggestionStatus === "error" ? (
                      <p className={styles.suggestionError}>
                        No pudimos crear este recordatorio.
                      </p>
                    ) : null}
                  </Card>
                ) : null}
              </div>
            ))}
            {pending ? (
              <p className={styles.meta}>
                Consultando fuentes y herramientas...
              </p>
            ) : null}
          </div>

          {error ? (
            <Notice
              tone="error"
              heading="No se pudo responder"
              className={styles.notice}
            >
              {error}
            </Notice>
          ) : null}

          <div className={styles.composerDock}>
            <form className={styles.composer} onSubmit={send}>
              <div className={styles.composerField}>
                <textarea
                  className={styles.composerInput}
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      if (
                        typeof event.currentTarget.form?.requestSubmit ===
                        "function"
                      ) {
                        event.currentTarget.form.requestSubmit();
                      }
                    }
                  }}
                  placeholder="Ej: Como ajusto el riego de mi Monstera?"
                  rows={1}
                  aria-label="Mensaje para el asistente"
                />
                <button
                  type="submit"
                  className={styles.composerSubmit}
                  disabled={pending || !message.trim()}
                >
                  <ArrowUpIcon
                    aria-hidden="true"
                    size="1.25rem"
                    weight="regular"
                    className={iconStyles.toneOnPrimary}
                  />
                  <span className={styles.composerSubmitLabel}>Enviar</span>
                </button>
              </div>
              <p className={styles.composerHint}>
                El asistente de IA puede cometer errores. Verifica la
                informacion importante.
              </p>
            </form>
          </div>
        </div>
      </div>

      {sources.length ? (
        <aside className={styles.sources} aria-label="Fuentes usadas">
          <p className={styles.eyebrow}>Fuentes usadas</p>
          <ul className={styles.sourcesList}>
            {sources.map((source) => (
              <li key={source.url} className={styles.sourcesItem}>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className={styles.sourceLink}
                >
                  <span className={styles.sourceTitle}>
                    {source.title || source.domain || source.url}
                  </span>
                  {source.domain ? (
                    <span className={styles.sourceDomain}>{source.domain}</span>
                  ) : null}
                </a>
              </li>
            ))}
          </ul>
        </aside>
      ) : null}
    </section>
  );
}

export function AssistantMessageContent({
  content,
  contentFormat = "plain_text",
}: {
  content: string;
  contentFormat?: AssistantMessageContentFormat | null;
}) {
  void contentFormat;
  return <span className={styles.messageContent}>{content}</span>;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

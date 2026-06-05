"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiClient, type AssistantReminderSuggestion, type AssistantSource, type ReminderCreate } from "@/lib/api/client";
import styles from "./AssistantChat.module.scss";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
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
  const secondaryContext = binomial && binomial !== plant ? binomial : null;
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<AssistantSource[]>([]);
  const [message, setMessage] = useState(plant ? `Tengo una consulta sobre ${plant}: ` : "");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [acceptingSuggestion, setAcceptingSuggestion] = useState<number | null>(null);

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
      setConversationId(response.conversation_id);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: response.message.content, reminderSuggestion: response.reminder_suggestion },
      ]);
      setSources(response.sources);
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : "No pudimos contactar al asistente.";
      setError(detail);
    } finally {
      setPending(false);
    }
  }

  async function acceptReminderSuggestion(suggestion: AssistantReminderSuggestion, messageIndex: number) {
    if (acceptingSuggestion !== null) return;
    setAcceptingSuggestion(messageIndex);
    setError(null);
    try {
      await apiClient.createReminder({
        garden_plant_id: suggestion.garden_plant_id,
        action: suggestion.action,
        date: suggestion.due_at.slice(0, 10),
        time: suggestion.due_at.slice(11, 16),
        recurrence: suggestion.recurrence,
        suggestion_justification: suggestion.suggestion_justification,
      });
      setMessages((current) => current.map((item, index) => (
        index === messageIndex ? { ...item, suggestionStatus: "accepted" } : item
      )));
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : "No pudimos crear el recordatorio sugerido.";
      setError(detail);
      setMessages((current) => current.map((item, index) => (
        index === messageIndex ? { ...item, suggestionStatus: "error" } : item
      )));
    } finally {
      setAcceptingSuggestion(null);
    }
  }

  return (
    <section className={styles.assistant}>
      <div className={styles.hero}>
        <p className={styles.eyebrow}>Asistente botanico</p>
        <h1>Pregunta con contexto.</h1>
        <p>Responde con evidencia, pide aclaraciones cuando falta informacion y no afirma acciones fallidas.</p>
        {plant ? (
          <p className={styles.meta}>
            Contexto inicial: {plant}
            {secondaryContext ? <><br /><em>{secondaryContext}</em></> : null}
          </p>
        ) : null}
      </div>

      <div className={styles.thread} aria-live="polite">
        {!messages.length ? <p className={styles.empty}>Hace una pregunta de cuidado, luz, plagas o recordatorios.</p> : null}
        {messages.map((item, index) => (
          <div className={styles.messageGroup} key={`${item.role}-${index}`}>
            <article
              className={`${styles.message} ${item.role === "user" ? styles.user : styles.assistantMessage}`}
            >
              {item.content}
            </article>
            {item.reminderSuggestion ? (
              <article className={styles.suggestionCard}>
                <p className={styles.eyebrow}>Recordatorio sugerido</p>
                <h2>{item.reminderSuggestion.action}</h2>
                <p>{item.reminderSuggestion.plant_name} · {formatDateTime(item.reminderSuggestion.due_at)} · {recurrenceLabels[item.reminderSuggestion.recurrence]}</p>
                <p>{item.reminderSuggestion.suggestion_justification}</p>
                <button
                  type="button"
                  onClick={() => acceptReminderSuggestion(item.reminderSuggestion!, index)}
                  disabled={acceptingSuggestion !== null || item.suggestionStatus === "accepted"}
                >
                  {item.suggestionStatus === "accepted" ? "Recordatorio creado" : acceptingSuggestion === index ? "Creando..." : "Aceptar sugerencia"}
                </button>
                {item.suggestionStatus === "error" ? <p className={styles.error}>No pudimos crear este recordatorio.</p> : null}
              </article>
            ) : null}
          </div>
        ))}
        {pending ? <p className={styles.meta}>Consultando fuentes y herramientas...</p> : null}
      </div>

      {error ? <p className={styles.error}>{error}</p> : null}

      <form className={styles.composer} onSubmit={send}>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ej: Como ajusto el riego de mi Monstera?"
        />
        <button type="submit" disabled={pending || !message.trim()}>
          Enviar
        </button>
      </form>

      {sources.length ? (
        <aside className={styles.sources}>
          <p className={styles.eyebrow}>Fuentes usadas</p>
          <ul>
            {sources.map((source) => (
              <li key={source.url}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title || source.domain || source.url}
                </a>
              </li>
            ))}
          </ul>
        </aside>
      ) : null}
    </section>
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiClient, type AssistantSource } from "@/lib/api/client";
import styles from "./AssistantChat.module.scss";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export function AssistantChat() {
  const searchParams = useSearchParams();
  const plant = searchParams.get("plant");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<AssistantSource[]>([]);
  const [message, setMessage] = useState(plant ? `Tengo una consulta sobre ${plant}: ` : "");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

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
      const response = await apiClient.sendAssistantMessage({ message: trimmed, conversation_id: conversationId, plant });
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, { role: "assistant", content: response.message.content }]);
      setSources(response.sources);
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : "No pudimos contactar al asistente.";
      setError(detail);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className={styles.assistant}>
      <div className={styles.hero}>
        <p className={styles.eyebrow}>Asistente botanico</p>
        <h1>Pregunta con contexto.</h1>
        <p>Responde con evidencia, pide aclaraciones cuando falta informacion y no afirma acciones fallidas.</p>
        {plant ? <p className={styles.meta}>Contexto inicial: {plant}</p> : null}
      </div>

      <div className={styles.thread} aria-live="polite">
        {!messages.length ? <p className={styles.empty}>Hace una pregunta de cuidado, luz, plagas o recordatorios.</p> : null}
        {messages.map((item, index) => (
          <article
            className={`${styles.message} ${item.role === "user" ? styles.user : styles.assistantMessage}`}
            key={`${item.role}-${index}`}
          >
            {item.content}
          </article>
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

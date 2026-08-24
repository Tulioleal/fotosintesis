import { describe, expect, it } from "vitest";
import { consumeAssistantStream } from "./api/client";

function sseResponse(frames: string[]) {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    body: {
      getReader() {
        return {
          read: async () => {
            if (index < frames.length) {
              const value = encoder.encode(frames[index]);
              index += 1;
              return { done: false, value };
            }
            return { done: true, value: undefined };
          },
        };
      },
    },
  } as unknown as Pick<Response, "body">;
}

describe("consumeAssistantStream", () => {
  it("forwards stage labels and resolves the terminal result without the type key", async () => {
    const labels: string[] = [];
    const terminal = await consumeAssistantStream(
      sseResponse([
        'data: {"type":"stage","stage_id":"retrieve","label_es":"Buscando evidencia","index":0}\n\n',
        ": ping\n\n",
        'data: {"type":"stage","stage_id":"generate_answer","label_es":"Redactando respuesta","index":1}\n\n',
        'data: {"type":"result","conversation_id":"c-1","message":{"role":"assistant","content":"Hola","content_format":"plain_text"},"sources":[],"requires_confirmation":false,"reminder_suggestion":null,"tool_failures":[]}\n\n',
      ]),
      (label) => labels.push(label),
    );

    expect(labels).toEqual(["Buscando evidencia", "Redactando respuesta"]);
    expect(terminal).toMatchObject({ conversation_id: "c-1" });
    expect((terminal as { type?: string }).type).toBeUndefined();
    expect("retryable" in terminal).toBe(false);
  });

  it("resolves retryable errors from the error terminal frame", async () => {
    const terminal = await consumeAssistantStream(
      sseResponse([
        'data: {"type":"error","retryable":true,"detail":"No model-generated assistant response could be produced. Please retry.","failure_category":"all_providers_failed"}\n\n',
      ]),
    );
    expect("retryable" in terminal && terminal.retryable).toBe(true);
  });

  it("throws when the stream ends without a terminal event", async () => {
    await expect(
      consumeAssistantStream(
        sseResponse(['data: {"type":"stage","stage_id":"retrieve","label_es":"x","index":0}\n\n']),
      ),
    ).rejects.toThrow(/without a terminal/);
  });
});

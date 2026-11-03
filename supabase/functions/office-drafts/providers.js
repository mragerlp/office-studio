export const providers = {
  openai: { label: "OpenAI", key: "STUDIO_OPENAI_MODELS" },
  anthropic: { label: "Claude", key: "STUDIO_ANTHROPIC_MODELS" },
  gemini: { label: "Gemini", key: "STUDIO_GEMINI_MODELS" },
  meta: { label: "Meta Muse", key: "STUDIO_META_MODELS" },
};

// Each fixed-host adapter returns one text draft and accepts no tool calls.
export function generationRequest(provider, model, key, instructions, prompt) {
  if (provider === "openai") {
    return {
      url: "https://api.openai.com/v1/responses",
      headers: { Authorization: "Bearer " + key },
      body: { model, store: false, max_output_tokens: 1024, instructions, input: prompt },
      text: (r) =>
        (r.output || []).filter((i) => i.type === "message").flatMap((i) => i.content || []).filter((p) =>
          p.type === "output_text"
        ).map((p) => p.text).join("\n"),
    };
  }
  if (provider === "anthropic") {
    return {
      url: "https://api.anthropic.com/v1/messages",
      headers: { "x-api-key": key, "anthropic-version": "2023-06-01" },
      body: { model, max_tokens: 1024, system: instructions, messages: [{ role: "user", content: prompt }] },
      text: (r) => (r.content || []).filter((p) => p.type === "text").map((p) => p.text).join("\n"),
    };
  }
  if (provider === "gemini") {
    return {
      url: "https://generativelanguage.googleapis.com/v1beta/models/" + encodeURIComponent(model) +
        ":generateContent",
      headers: { "x-goog-api-key": key },
      body: {
        systemInstruction: { parts: [{ text: instructions }] },
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: { maxOutputTokens: 1024 },
      },
      text: (r) =>
        (r.candidates?.[0]?.content?.parts || []).filter((p) => !p.thought && typeof p.text === "string").map(
          (p) => p.text,
        ).join("\n"),
    };
  }
  if (provider === "meta") {
    return {
      url: "https://api.meta.ai/v1/chat/completions",
      headers: { Authorization: "Bearer " + key },
      body: {
        model,
        max_completion_tokens: 1024,
        messages: [{ role: "developer", content: instructions }, { role: "user", content: prompt }],
      },
      text: (r) => r.choices?.[0]?.message?.content,
    };
  }
  throw new Error("Unknown provider.");
}

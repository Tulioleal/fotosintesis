export interface AssistantHrefValues {
  plant?: string | null;
  binomial?: string | null;
  scientific?: string | null;
}

export function buildAssistantHref(values: AssistantHrefValues): string {
  const params = Object.entries(values)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].length > 0)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join("&");
  return `/assistant${params ? `?${params}` : ""}`;
}

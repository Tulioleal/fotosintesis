export function browserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

export function effectiveTimezone(reminderTimezone?: string | null): string {
  return reminderTimezone || browserTimezone();
}

const dueDateFormatterCache = new Map<string, Intl.DateTimeFormat>();

export function formatDueDate(iso: string, timezone?: string | null): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const zone = effectiveTimezone(timezone);
  let formatter = dueDateFormatterCache.get(zone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("es-AR", {
      timeZone: zone,
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
    dueDateFormatterCache.set(zone, formatter);
  }
  return formatter.format(date).replace(".", "");
}

export const TIMEZONE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "UTC", label: "UTC" },
  { value: "America/Argentina/Buenos_Aires", label: "Argentina (Buenos Aires)" },
  { value: "America/New_York", label: "EE.UU. (Nueva York)" },
  { value: "America/Los_Angeles", label: "EE.UU. (Los Ángeles)" },
  { value: "America/Chicago", label: "EE.UU. (Chicago)" },
  { value: "America/Denver", label: "EE.UU. (Denver)" },
  { value: "America/Mexico_City", label: "México (Ciudad de México)" },
  { value: "America/Sao_Paulo", label: "Brasil (São Paulo)" },
  { value: "America/Bogota", label: "Colombia (Bogotá)" },
  { value: "America/Lima", label: "Perú (Lima)" },
  { value: "America/Santiago", label: "Chile (Santiago)" },
  { value: "America/Montevideo", label: "Uruguay (Montevideo)" },
  { value: "America/Asuncion", label: "Paraguay (Asunción)" },
  { value: "America/La_Paz", label: "Bolivia (La Paz)" },
  { value: "America/Guayaquil", label: "Ecuador (Guayaquil)" },
  { value: "America/Caracas", label: "Venezuela (Caracas)" },
  { value: "America/Havana", label: "Cuba (La Habana)" },
  { value: "Europe/Madrid", label: "España (Madrid)" },
  { value: "Europe/London", label: "Reino Unido (Londres)" },
  { value: "Europe/Paris", label: "Francia (París)" },
  { value: "Europe/Berlin", label: "Alemania (Berlín)" },
  { value: "Europe/Rome", label: "Italia (Roma)" },
  { value: "Europe/Lisbon", label: "Portugal (Lisboa)" },
  { value: "Africa/Cairo", label: "Egipto (El Cairo)" },
  { value: "Asia/Tokyo", label: "Japón (Tokio)" },
  { value: "Asia/Shanghai", label: "China (Shanghái)" },
  { value: "Asia/Kolkata", label: "India (Kolkata)" },
  { value: "Asia/Singapore", label: "Singapur" },
  { value: "Australia/Sydney", label: "Australia (Sídney)" },
  { value: "Pacific/Auckland", label: "Nueva Zelanda (Auckland)" },
];

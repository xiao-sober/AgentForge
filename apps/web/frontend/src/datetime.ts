const BEIJING_TIME_ZONE = "Asia/Shanghai";

interface DateParts {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
}

export function formatBeijingDateTime(value?: string | null): string {
  const parts = dateParts(value);
  if (!parts) {
    return value || "-";
  }
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} UTC+8`;
}

export function formatBeijingShort(value?: string | null): string {
  const parts = dateParts(value);
  if (!parts) {
    return value || "-";
  }
  return `${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}

function dateParts(value?: string | null): DateParts | null {
  const date = parseDate(value);
  if (!date) {
    return null;
  }
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    timeZone: BEIJING_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
  const parts = Object.fromEntries(formatter.formatToParts(date).map((part) => [part.type, part.value]));
  return {
    year: parts.year || "0000",
    month: parts.month || "00",
    day: parts.day || "00",
    hour: parts.hour || "00",
    minute: parts.minute || "00",
    second: parts.second || "00"
  };
}

function parseDate(value?: string | null): Date | null {
  const raw = value?.trim();
  if (!raw) {
    return null;
  }
  const normalized = hasTimeZone(raw) ? raw : `${raw}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function hasTimeZone(value: string): boolean {
  return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
}

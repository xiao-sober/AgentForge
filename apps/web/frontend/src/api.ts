const API_PREFIX = "/api";

export function apiUrl(url: string | undefined): string | undefined {
  if (!url) {
    return undefined;
  }
  if (/^https?:\/\//.test(url)) {
    return url;
  }
  if (url === API_PREFIX || url.startsWith(`${API_PREFIX}/`)) {
    return url;
  }
  if (url.startsWith("/")) {
    return `${API_PREFIX}${url}`;
  }
  return `${API_PREFIX}/${url}`;
}

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(apiUrl(url) || url);
  const payload = (await response.json()) as { error?: string };
  if (!response.ok) {
    throw new Error(payload.error || `GET ${url} failed`);
  }
  return payload as T;
}

export async function postJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(apiUrl(url) || url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = (await response.json()) as { error?: string };
  if (!response.ok) {
    throw new Error(data.error || `POST ${url} failed`);
  }
  return data as T;
}

import type { UploadedFileRecord } from "./types";

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
  const payload = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload.error || `GET ${url} failed: ${response.status} ${response.statusText}`.trim());
  }
  return payload as T;
}

export async function postJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(apiUrl(url) || url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(data.error || `POST ${url} failed: ${response.status} ${response.statusText}`.trim());
  }
  return data as T;
}

export async function uploadFiles(files: File[]): Promise<{ uploads: UploadedFileRecord[] }> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch(apiUrl("/uploads") || "/api/uploads", {
    method: "POST",
    body: formData
  });
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    throw new Error(data.error || `Upload failed: ${response.status} ${response.statusText}`.trim());
  }
  return data as { uploads: UploadedFileRecord[] };
}

async function parseJsonResponse(response: Response): Promise<{ error?: string } & Record<string, unknown>> {
  const text = await response.text();
  if (!text.trim()) {
    return {};
  }
  try {
    return JSON.parse(text) as { error?: string } & Record<string, unknown>;
  } catch {
    if (!response.ok) {
      return { error: `HTTP ${response.status} ${response.statusText || "response was not JSON"}`.trim() };
    }
    throw new Error("API response was not valid JSON.");
  }
}

import type { Plan } from "./types";

const configuredApiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

/** Absolute backend URL for server-side fetches (RSC / Node). */
export const SERVER_API_URL = configuredApiUrl;

/**
 * Browser calls use same-origin paths so Next.js rewrites proxy to the backend
 * and avoid CORS issues when the frontend runs on a non-3000 port.
 */
export const API_URL = "";

export const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL;

export function publicShareUrl(token: string): string {
  if (typeof window !== "undefined" && !BASE_URL) {
    return `${window.location.origin}/plan/${token}`;
  }
  return `${BASE_URL ?? "http://localhost:3000"}/plan/${token}`;
}

export async function consumePlanStream(
  response: Response,
  onStatus: (value: string) => void,
): Promise<{ plan: Plan; token: string; ma_phien: string; phien_ban: number }> {
  if (!response.ok) {
    const text = await response.text();
    let detail = "Không thể tạo kế hoạch";
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
      else if (text) detail = text;
    } catch {
      if (text) detail = text;
    }
    throw new Error(detail);
  }
  if (!response.body) throw new Error("Trình duyệt không hỗ trợ nhận tiến trình");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: any;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    if (done && buffer.trim()) {
      blocks.push(buffer);
      buffer = "";
    }
    for (const block of blocks) {
      const event = block.match(/^event: (.+)$/m)?.[1];
      const raw = block.match(/^data: (.+)$/m)?.[1];
      if (!raw) continue;
      const data = JSON.parse(raw);
      if (event === "status") {
        if (typeof data.status !== "string") throw new Error("Malformed status event");
        onStatus(data.status);
      }
      if (event === "error") {
        const detail =
          data && typeof data.detail === "string" && data.detail.trim()
            ? data.detail.trim()
            : "Không thể tạo kế hoạch";
        throw new Error(detail);
      }
      if (event === "result") {
        if (result) throw new Error("Duplicate result event");
        result = data;
      }
    }
    if (result) {
      await reader.cancel();
      return result;
    }
    if (done) break;
  }
  if (!result) throw new Error("Máy chủ không trả kế hoạch");
  return result;
}

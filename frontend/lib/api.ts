import type { Plan } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function consumePlanStream(
  response: Response,
  onStatus: (value: string) => void,
): Promise<{ plan: Plan; token: string; ma_phien: string; phien_ban: number }> {
  if (!response.ok) {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text);
      throw new Error(parsed.detail ?? text);
    } catch {
      if (!text.startsWith("{")) throw new Error(text || "Không thể tạo kế hoạch");
      const parsed = JSON.parse(text);
      throw new Error(parsed.detail ?? "Không thể tạo kế hoạch");
    }
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
    if(done&&buffer.trim()){blocks.push(buffer);buffer=""}
    for (const block of blocks) {
      const event = block.match(/^event: (.+)$/m)?.[1];
      const raw = block.match(/^data: (.+)$/m)?.[1];
      if (!raw) continue;
      const data = JSON.parse(raw);
      if (event === "status") {
        if(typeof data.status!=="string")throw new Error("Malformed status event");
        onStatus(data.status);
      }
      if (event === "error") throw new Error("Plan generation failed");
      if (event === "result") {
        if(result)throw new Error("Duplicate result event");
        result = data;
      }
    }
    if(result){await reader.cancel();return result}
    if (done) break;
  }
  if (!result) throw new Error("Máy chủ không trả kế hoạch");
  return result;
}

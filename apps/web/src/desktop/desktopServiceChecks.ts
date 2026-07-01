/** Local service health for the desktop panel — browser fetch only (no Tauri subprocess probes). */

export type ServiceCheck = { ok: boolean; detail: string };

export type DesktopServiceStatus = {
  ollama: ServiceCheck;
  comfy: ServiceCheck;
  api: ServiceCheck;
};

async function probe(url: string, label: string): Promise<ServiceCheck> {
  try {
    const response = await fetch(url, {
      method: "GET",
      signal: AbortSignal.timeout(4000),
    });
    if (response.ok) {
      return { ok: true, detail: `HTTP ${response.status}` };
    }
    return { ok: false, detail: `${label}: HTTP ${response.status}` };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, detail: message };
  }
}

export async function fetchDesktopServiceStatus(): Promise<DesktopServiceStatus> {
  const [ollama, comfy, api] = await Promise.all([
    probe("http://127.0.0.1:11434/api/tags", "Ollama"),
    probe("http://127.0.0.1:8188/system_stats", "ComfyUI"),
    probe("http://127.0.0.1:8787/api/studio/health", "Studio API"),
  ]);
  return { ollama, comfy, api };
}

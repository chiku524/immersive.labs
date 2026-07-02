/** Local service health for the desktop panel.
 *
 * Probes run in Rust (Tauri command) rather than browser fetch: Ollama and ComfyUI do not send
 * CORS headers for the WebView origin (http://tauri.localhost), so a direct fetch is blocked and
 * would always report "down" even when the services are healthy. The Rust side has no CORS
 * restriction and does not spawn a console window.
 */
import { invoke } from "@tauri-apps/api/core";

export type ServiceCheck = { ok: boolean; detail: string };

export type DesktopServiceStatus = {
  ollama: ServiceCheck;
  comfy: ServiceCheck;
  api: ServiceCheck;
};

export async function fetchDesktopServiceStatus(): Promise<DesktopServiceStatus> {
  return await invoke<DesktopServiceStatus>("check_services");
}

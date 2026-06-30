import { isTauriRuntime } from "../tauriRuntime";

/** Save a job pack in the browser (anchor download) or via native save dialog in Tauri. */
export async function saveJobPackZip(jobId: string, blob?: Blob): Promise<string | null> {
  const filename = `immersive-studio-${jobId}.zip`;

  if (isTauriRuntime()) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<string>("save_job_pack_zip", { jobId });
  }

  if (!blob) {
    throw new Error("Missing pack data for download.");
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return null;
}

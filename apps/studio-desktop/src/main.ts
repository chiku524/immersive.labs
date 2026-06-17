import { invoke } from "@tauri-apps/api/core";

type ServiceCheck = { ok: boolean; detail: string };
type BlenderCheck = ServiceCheck & { path?: string | null };
type PrereqStatus = {
  ollama: ServiceCheck;
  comfy: ServiceCheck;
  api: ServiceCheck;
  blender: BlenderCheck;
  docker: ServiceCheck;
  repo_root: string;
  comfy_root?: string | null;
};

type DesktopSettings = {
  autoStartApi: boolean;
  autoStartComfy: boolean;
  closeToTray: boolean;
  openStudioWhenReady: boolean;
};

const checksEl = document.querySelector<HTMLUListElement>("#checks")!;
const statusEl = document.querySelector<HTMLParagraphElement>("#status")!;
const openStudioBtn = document.querySelector<HTMLButtonElement>("#open-studio")!;
const refreshBtn = document.querySelector<HTMLButtonElement>("#refresh")!;
const startApiBtn = document.querySelector<HTMLButtonElement>("#start-api")!;
const startComfyBtn = document.querySelector<HTMLButtonElement>("#start-comfy")!;
const openJobsBtn = document.querySelector<HTMLButtonElement>("#open-jobs")!;

const optAutoApi = document.querySelector<HTMLInputElement>("#opt-auto-api")!;
const optAutoComfy = document.querySelector<HTMLInputElement>("#opt-auto-comfy")!;
const optCloseTray = document.querySelector<HTMLInputElement>("#opt-close-tray")!;
const optOpenStudio = document.querySelector<HTMLInputElement>("#opt-open-studio")!;

function setStatus(message: string) {
  statusEl.textContent = message;
}

function renderChecks(status: PrereqStatus) {
  const rows: Array<[string, ServiceCheck | BlenderCheck]> = [
    ["Studio API", status.api],
    ["Ollama", status.ollama],
    ["Blender", status.blender],
    ["ComfyUI", status.comfy],
    ["Docker (optional)", status.docker],
  ];

  checksEl.innerHTML = rows
    .map(([name, row]) => {
      const klass = row.ok ? "ok" : "bad";
      const suffix = "path" in row && row.path ? ` — ${row.path}` : "";
      return `<li class="${klass}"><span class="name">${name}</span><span class="detail">${row.detail}${suffix}</span></li>`;
    })
    .join("");

  if (status.comfy_root) {
    checksEl.innerHTML += `<li class="hint-row"><span class="name">Comfy path</span><span class="detail">${status.comfy_root}</span></li>`;
  }

  openStudioBtn.disabled = !status.api.ok;
}

async function refreshChecks() {
  setStatus("Checking local services…");
  try {
    const status = await invoke<PrereqStatus>("check_prerequisites");
    renderChecks(status);
    setStatus(status.api.ok ? "Studio API is ready." : "Start the Studio API, then open Studio.");
  } catch (err) {
    setStatus(`Check failed: ${String(err)}`);
  }
}

function readSettingsFromForm(): DesktopSettings {
  return {
    autoStartApi: optAutoApi.checked,
    autoStartComfy: optAutoComfy.checked,
    closeToTray: optCloseTray.checked,
    openStudioWhenReady: optOpenStudio.checked,
  };
}

function applySettingsToForm(settings: DesktopSettings) {
  optAutoApi.checked = settings.autoStartApi;
  optAutoComfy.checked = settings.autoStartComfy;
  optCloseTray.checked = settings.closeToTray;
  optOpenStudio.checked = settings.openStudioWhenReady;
}

async function persistSettings() {
  try {
    await invoke("save_settings", { settings: readSettingsFromForm() });
    setStatus("Settings saved.");
  } catch (err) {
    setStatus(`Failed to save settings: ${String(err)}`);
  }
}

async function loadSettings() {
  try {
    const settings = await invoke<DesktopSettings>("get_settings");
    applySettingsToForm(settings);
  } catch {
    /* defaults in HTML */
  }
}

for (const input of [optAutoApi, optAutoComfy, optCloseTray, optOpenStudio]) {
  input.addEventListener("change", () => {
    void persistSettings();
  });
}

refreshBtn.addEventListener("click", () => {
  void refreshChecks();
});

startApiBtn.addEventListener("click", () => {
  void (async () => {
    setStatus("Starting Studio API…");
    try {
      const message = await invoke<string>("start_worker");
      setStatus(message);
      await refreshChecks();
    } catch (err) {
      setStatus(`Failed to start API: ${String(err)}`);
    }
  })();
});

startComfyBtn.addEventListener("click", () => {
  void (async () => {
    setStatus("Starting ComfyUI…");
    try {
      const message = await invoke<string>("start_comfy");
      setStatus(message);
      await refreshChecks();
    } catch (err) {
      setStatus(`Failed to start ComfyUI: ${String(err)}`);
    }
  })();
});

openStudioBtn.addEventListener("click", () => {
  void (async () => {
    setStatus("Opening Studio…");
    try {
      const message = await invoke<string>("open_studio");
      setStatus(message);
    } catch (err) {
      setStatus(`Failed to open Studio: ${String(err)}`);
    }
  })();
});

openJobsBtn.addEventListener("click", () => {
  void invoke("open_jobs_folder").catch((err) => {
    setStatus(`Failed to open jobs folder: ${String(err)}`);
  });
});

void loadSettings();
void refreshChecks();
window.setInterval(() => void refreshChecks(), 12_000);

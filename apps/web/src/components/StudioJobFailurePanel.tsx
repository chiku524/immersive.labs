import "./StudioJobFailurePanel.css";

export type JobFailureKind = "json" | "gateway" | "tripo" | "timeout" | "auth" | "generic";

export type ClassifiedJobFailure = {
  kind: JobFailureKind;
  title: string;
  hint: string;
};

export function classifyJobFailure(message: string): ClassifiedJobFailure {
  const m = message.trim();
  if (/No JSON object found/i.test(m) || /not valid JSON/i.test(m) || /Top-level JSON must be an object/i.test(m)) {
    return {
      kind: "json",
      title: "Spec generation failed (model output)",
      hint: "The local LLM did not return usable JSON. Retry with Mock off after `ollama pull` of your model, shorten the prompt, or enable Mock for a deterministic pack.",
    };
  }
  if (
    /Gateway or tunnel returned HTTP/i.test(m) ||
    /gateway_status/i.test(m) ||
    /invalid JSON.*502/i.test(m) ||
    /HTTP 502|HTTP 503|HTTP 504|HTTP 524/i.test(m)
  ) {
    return {
      kind: "gateway",
      title: "Lost contact with the Studio API",
      hint: "The job may still be running on the worker. Wait and refresh Recent jobs, or check tunnel/origin health if this persists.",
    };
  }
  if (/tripo/i.test(m) && (/credit|api key|401|403|tsk_|tcli_/i.test(m) || /unavailable/i.test(m))) {
    return {
      kind: "tripo",
      title: "Tripo mesh step failed",
      hint: "Confirm STUDIO_TRIPO_API_KEY is an OpenAPI key (tsk_…), not a client id (tcli_…), and that OpenAPI credits remain at platform.tripo3d.ai.",
    };
  }
  if (/timed out|timeout/i.test(m)) {
    return {
      kind: "timeout",
      title: "Job timed out",
      hint: "Raise STUDIO_OLLAMA_READ_TIMEOUT_S / Comfy wait envs, or split the queue worker from the API so long jobs do not starve health checks.",
    };
  }
  if (/Unauthorized|API key|Forbidden/i.test(m)) {
    return {
      kind: "auth",
      title: "Authentication failed",
      hint: "Paste a valid Studio API key above, or disable auth on a local worker for desktop use.",
    };
  }
  return {
    kind: "generic",
    title: "Job failed",
    hint: "See the worker error below. Retry the job after fixing the underlying service (Ollama, ComfyUI, Tripo, or Blender).",
  };
}

type Props = {
  message: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

export function StudioJobFailurePanel({ message, onDismiss, onRetry }: Props) {
  const classified = classifyJobFailure(message);
  return (
    <section
      className={`studio-job-failure studio-job-failure--${classified.kind}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="studio-job-failure-header">
        <h2 className="studio-job-failure-title">{classified.title}</h2>
        <div className="studio-job-failure-actions">
          {onRetry ? (
            <button type="button" className="btn btn-primary studio-job-failure-btn" onClick={onRetry}>
              Retry
            </button>
          ) : null}
          {onDismiss ? (
            <button type="button" className="btn btn-ghost studio-job-failure-btn" onClick={onDismiss}>
              Dismiss
            </button>
          ) : null}
        </div>
      </div>
      <p className="studio-job-failure-hint">{classified.hint}</p>
      <p className="studio-job-failure-label">last_error</p>
      <pre className="studio-job-failure-text">{message}</pre>
    </section>
  );
}

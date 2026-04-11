import { useEffect } from "react";
import { Link } from "react-router-dom";
import { EngravedBackdrop } from "../components/EngravedBackdrop";
import "../App.css";
import "./DocsPage.css";

const DOC_TITLE = "Documentation — Immersive Labs";
const DEFAULT_TITLE = "Immersive Labs — Digital Product Studio";

export function DocsPage() {
  useEffect(() => {
    document.title = DOC_TITLE;
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, []);

  return (
    <>
      <EngravedBackdrop />
      <div className="page docs-page">
        <header className="header">
          <Link className="logo" to="/">
            <img className="logo-mark-img" src="/brand-mark.png" alt="" width={32} height={32} />
            Immersive Labs
          </Link>
          <nav className="nav" aria-label="Primary">
            <Link to="/">Home</Link>
            <Link to="/studio">Game studio</Link>
            <Link to="/docs" className="nav-active">
              Docs
            </Link>
          </nav>
        </header>

        <main id="documentation-main">
          <article
            className="docs-article"
            itemScope
            itemType="https://schema.org/TechArticle"
            aria-labelledby="docs-heading"
          >
            <meta itemProp="name" content="Immersive Labs — Studio documentation" />
            <div className="docs-hero">
              <p className="eyebrow">Guides &amp; reference</p>
              <h1 id="docs-heading" className="docs-title">
                Studio documentation
              </h1>
              <p className="docs-subtitle" itemProp="description">
                Everything you need to run the Video Game Generation Studio: local development, the web UI, the Python
                worker, ComfyUI textures, Blender mesh export, deployment on Google Cloud with Cloudflare Tunnel, and
                Unity import. Deep-dive Markdown in the monorepo mirrors and extends this page.
              </p>
            </div>

            <div className="docs-layout">
              <aside className="docs-toc" aria-label="On this page">
                <h2 className="docs-toc-title">Contents</h2>
                <nav aria-label="Documentation sections">
                  <ol>
                    <li>
                      <a href="#overview">Overview</a>
                    </li>
                    <li>
                      <a href="#quick-start">Quick start</a>
                    </li>
                    <li>
                      <a href="#studio-ui">Studio UI</a>
                    </li>
                    <li>
                      <a href="#worker">Worker &amp; API</a>
                    </li>
                    <li>
                      <a href="#comfyui">ComfyUI &amp; textures</a>
                    </li>
                    <li>
                      <a href="#blender">Blender &amp; mesh</a>
                    </li>
                    <li>
                      <a href="#deploy">GCP &amp; Cloudflare</a>
                    </li>
                    <li>
                      <a href="#environment">Environment variables</a>
                    </li>
                    <li>
                      <a href="#unity">Unity import</a>
                    </li>
                    <li>
                      <a href="#repository-docs">Repository documentation</a>
                    </li>
                  </ol>
                </nav>
              </aside>

              <div className="docs-body">
                <section id="overview" className="docs-section" aria-labelledby="overview-heading">
                  <h2 id="overview-heading">Overview</h2>
                  <p>
                    The studio turns a text prompt into a <strong>validated asset specification</strong>, optional{" "}
                    <strong>PBR textures</strong> (via ComfyUI), an optional <strong>placeholder mesh</strong> (via
                    Blender), and a downloadable <strong>Unity-oriented pack</strong> (<code>manifest.json</code>,{" "}
                    <code>spec.json</code>, <code>pack.zip</code>). The <strong>browser</strong> never runs ComfyUI or
                    Blender; a separate <strong>Python worker</strong> does.
                  </p>
                  <p className="docs-note" role="note">
                    <strong>Split deploy:</strong> the marketing site and <Link to="/studio">/studio</Link> are static
                    (e.g. Vercel). The worker runs on a VM or container with persistent disk for SQLite and job output.
                    Point <code>VITE_STUDIO_API_URL</code> at the worker&apos;s public HTTPS origin.
                  </p>
                </section>

                <section id="quick-start" className="docs-section" aria-labelledby="quick-start-heading">
                  <h2 id="quick-start-heading">Quick start (developers)</h2>
                  <ol>
                    <li>
                      From the repository root: <code>npm install</code> then <code>npm run dev</code>.
                    </li>
                    <li>
                      Open <code>http://localhost:5173/studio</code> (Vite dev server defaults).
                    </li>
                    <li>
                      In another terminal, under <code>apps/studio-worker</code>: create a venv,{" "}
                      <code>pip install -e .</code>, then{" "}
                      <code>immersive-studio serve --host 127.0.0.1 --port 8787</code>.
                    </li>
                    <li>
                      Ensure <code>VITE_STUDIO_API_URL=http://127.0.0.1:8787</code> for the web app (e.g.{" "}
                      <code>apps/web/.env.development.local</code>) if the default is wrong.
                    </li>
                    <li>
                      Use <strong>mock</strong> mode in the UI if Ollama is not running. Enable textures only when
                      ComfyUI is up; enable mesh export only when Blender is installed or configured.
                    </li>
                  </ol>
                </section>

                <section id="studio-ui" className="docs-section" aria-labelledby="studio-ui-heading">
                  <h2 id="studio-ui-heading">Studio UI</h2>
                  <p>
                    The <Link to="/studio">Game studio</Link> page drives spec generation, full jobs, pack export, and
                    billing (when enabled). It shows <strong>worker health</strong>,{" "}
                    <strong>ComfyUI reachability</strong>, usage limits, and a <strong>job list</strong> with downloads.
                  </p>
                  <h3>Authentication</h3>
                  <p>
                    If the operator sets <code>STUDIO_API_AUTH_REQUIRED=1</code>, store an API key in the browser (saved
                    in <code>localStorage</code>) and send it on API requests.
                  </p>
                  <h3>CORS</h3>
                  <p>
                    Every browser origin you use (apex, <code>www</code>, Vercel preview, etc.) must appear in{" "}
                    <code>STUDIO_CORS_ORIGINS</code> on the worker, as a comma-separated list (scheme + host, no path).
                  </p>
                </section>

                <section id="worker" className="docs-section" aria-labelledby="worker-heading">
                  <h2 id="worker-heading">Worker &amp; HTTP API</h2>
                  <p>
                    The worker is the <strong>immersive-studio</strong> package: CLI, SDK, and FastAPI app. Install from{" "}
                    <a href="https://pypi.org/project/immersive-studio/" target="_blank" rel="noopener noreferrer">
                      PyPI
                    </a>{" "}
                    (<code>pipx install immersive-studio</code>) or from a clone with <code>pip install -e .</code> under{" "}
                    <code>apps/studio-worker</code>.
                  </p>
                  <p>Common endpoints include:</p>
                  <ul>
                    <li>
                      <code>GET /api/studio/health</code> — liveness; use for monitors.
                    </li>
                    <li>
                      <code>GET /api/studio/comfy-status</code> — probes ComfyUI using <code>STUDIO_COMFY_URL</code>.
                    </li>
                    <li>
                      <code>POST /api/studio/jobs/run</code> — synchronous full job (spec + pack + optional textures /
                      mesh).
                    </li>
                    <li>
                      <code>GET /api/studio/jobs</code> — job index (auth when required).
                    </li>
                  </ul>
                  <p>
                    Full route tables and Stripe webhooks are documented in{" "}
                    <code>apps/studio-worker/README.md</code> in the repository.
                  </p>
                </section>

                <section id="comfyui" className="docs-section" aria-labelledby="comfyui-heading">
                  <h2 id="comfyui-heading">ComfyUI &amp; textures</h2>
                  <p>
                    Texture jobs call ComfyUI&apos;s HTTP API (<code>/prompt</code>, <code>/history</code>,{" "}
                    <code>/view</code>). Set <code>STUDIO_COMFY_URL</code> to the <strong>base URL</strong> the worker can
                    reach (no trailing slash).
                  </p>
                  <ul>
                    <li>
                      <strong>Default (unset <code>STUDIO_COMFY_URL</code>):</strong> the worker uses the hosted API at{" "}
                      <code>https://comfy.immersivelabs.space</code> so CLI and SDK work without a local ComfyUI. Override
                      for self-hosted or local dev.
                    </li>
                    <li>
                      <strong>Local dev:</strong> <code>STUDIO_COMFY_URL=http://127.0.0.1:8188</code> when ComfyUI runs on
                      the same machine as the worker.
                    </li>
                    <li>
                      <strong>Worker in Docker, ComfyUI on the VM host:</strong> use the public URL (e.g.{" "}
                      <code>https://comfy.immersivelabs.space</code>), not <code>http://127.0.0.1:8188</code> — inside a
                      container, <code>127.0.0.1</code> is the container itself, not the host. Alternatively{" "}
                      <code>http://host.docker.internal:8188</code> with Docker&apos;s host-gateway mapping.
                    </li>
                    <li>
                      <strong>Remote ComfyUI:</strong> set <code>STUDIO_COMFY_URL</code> to that HTTPS origin; ensure
                      checkpoints match <code>STUDIO_COMFY_CHECKPOINT</code> and profile <code>STUDIO_COMFY_PROFILE</code>{" "}
                      (<code>sd15</code> or <code>sdxl</code>).
                    </li>
                  </ul>
                  <p>
                    Workflow JSON and checkpoint notes: <code>apps/studio-worker/comfy/README.md</code>. Verify with{" "}
                    <code>immersive-studio doctor</code> or <code>python -m studio_worker.cli doctor</code>.
                  </p>
                </section>

                <section id="blender" className="docs-section" aria-labelledby="blender-heading">
                  <h2 id="blender-heading">Blender &amp; mesh export</h2>
                  <p>
                    Optional <strong>placeholder GLB</strong> export runs Blender as a <strong>subprocess</strong> on
                    the worker (not a public URL like ComfyUI). The <strong>official Docker image</strong> installs Blender
                    so end users do not install it. On a bare-metal worker, install Blender or set{" "}
                    <code>STUDIO_BLENDER_BIN</code>. Enable <strong>Export mesh</strong> in the UI or{" "}
                    <code>STUDIO_EXPORT_MESH_DEFAULT=1</code> for API defaults.
                  </p>
                </section>

                <section id="deploy" className="docs-section" aria-labelledby="deploy-heading">
                  <h2 id="deploy-heading">Google Cloud &amp; Cloudflare Tunnel</h2>
                  <p>
                    A typical production path uses an <strong>e2-micro</strong> VM (within free-tier limits when
                    eligible), <strong>Docker</strong> for the worker image, and a <strong>Cloudflare Tunnel</strong> so
                    browsers reach <code>https://…</code> without opening GCP firewall ports for the API.
                  </p>
                  <h3>Worker API hostname</h3>
                  <p>
                    Bind the container to <code>127.0.0.1:8787</code>. Map a hostname (e.g.{" "}
                    <code>api-origin.immersivelabs.space</code>) in Zero Trust → Tunnels → Public hostnames →{" "}
                    <code>http://127.0.0.1:8787</code>. A Cloudflare Worker may front <code>api.…</code> with{" "}
                    <code>ORIGIN_URL</code> pointing at that origin — see <code>apps/studio-edge/README.md</code>.
                  </p>
                  <h3>ComfyUI hostname</h3>
                  <p>
                    If ComfyUI runs on the <strong>same VM</strong>, listen on <code>127.0.0.1:8188</code> and add a
                    second public hostname (e.g. <code>comfy.…</code>) → <code>http://127.0.0.1:8188</code>. Keep{" "}
                    <code>STUDIO_COMFY_URL=http://127.0.0.1:8188</code> on the worker. Create DNS in the correct
                    Cloudflare zone (use the tunnel UI or <code>cloudflared tunnel route dns</code> with the account that
                    owns the domain).
                  </p>
                  <h3>GCE metadata bootstrap</h3>
                  <p>
                    The repo ships <code>scripts/studio-cloudflare-tunnel/vm-bootstrap-gce-startup.sh</code> for
                    instance startup: swap, Docker, clone/build, and <code>docker run</code> with{" "}
                    <code>STUDIO_CORS_ORIGINS</code> and <code>STUDIO_COMFY_URL</code> from metadata. Use{" "}
                    <code>--metadata-from-file=STUDIO_CORS_ORIGINS=…</code> when values contain commas.
                  </p>
                  <p>
                    Step-by-step checklist: <code>docs/studio/deploy-gcp-free-vm.md</code>. Operator scripts index:{" "}
                    <code>scripts/studio-cloudflare-tunnel/README.md</code>.
                  </p>
                </section>

                <section id="environment" className="docs-section" aria-labelledby="environment-heading">
                  <h2 id="environment-heading">Environment variables (selected)</h2>
                  <dl className="docs-dl">
                    <div>
                      <dt>
                        <code>VITE_STUDIO_API_URL</code> (frontend build)
                      </dt>
                      <dd>Public HTTPS base URL of the worker; set before Vite build (e.g. Vercel env).</dd>
                    </div>
                    <div>
                      <dt>
                        <code>STUDIO_CORS_ORIGINS</code>
                      </dt>
                      <dd>Comma-separated allowed browser origins for the Studio API.</dd>
                    </div>
                    <div>
                      <dt>
                        <code>STUDIO_COMFY_URL</code>
                      </dt>
                      <dd>ComfyUI base URL for texture jobs.</dd>
                    </div>
                    <div>
                      <dt>
                        <code>STUDIO_COMFY_CHECKPOINT</code> / <code>STUDIO_COMFY_PROFILE</code>
                      </dt>
                      <dd>Checkpoint filename and workflow profile (<code>sd15</code> / <code>sdxl</code>).</dd>
                    </div>
                    <div>
                      <dt>
                        <code>STUDIO_OLLAMA_URL</code> / <code>STUDIO_OLLAMA_MODEL</code>
                      </dt>
                      <dd>LLM for real spec generation when not using mock mode.</dd>
                    </div>
                    <div>
                      <dt>
                        <code>STUDIO_BLENDER_BIN</code>
                      </dt>
                      <dd>Path to Blender if not on <code>PATH</code>.</dd>
                    </div>
                    <div>
                      <dt>
                        <code>STUDIO_API_AUTH_REQUIRED</code>
                      </dt>
                      <dd>
                        Set to <code>1</code> for API keys and tenant isolation.
                      </dd>
                    </div>
                  </dl>
                  <p>
                    Full tables: <code>apps/studio-worker/README.md</code> and <code>docs/studio/essentials.md</code>.
                  </p>
                </section>

                <section id="unity" className="docs-section" aria-labelledby="unity-heading">
                  <h2 id="unity-heading">Unity import</h2>
                  <p>
                    Use the UPM package <code>com.immersivelabs.studio</code> (<code>packages/studio-unity</code>) to
                    import packs into a URP project: materials from generated textures, folder layout per{" "}
                    <code>manifest.json</code>, and optional colliders from the spec.
                  </p>
                  <p>
                    Conventions: <code>docs/studio/unity-export-conventions.md</code>. Package README:{" "}
                    <code>packages/studio-unity/README.md</code>.
                  </p>
                </section>

                <section id="repository-docs" className="docs-section" aria-labelledby="repository-docs-heading">
                  <h2 id="repository-docs-heading">Repository documentation</h2>
                  <p>
                    The monorepo is the source of truth for long-form guides. Start with the platform manual and
                    essentials, then drill into worker, ComfyUI, deployment, and security docs as needed.
                  </p>
                  <ul>
                    <li>
                      <strong>Platform manual (TOC, deployment, APIs):</strong> <code>docs/studio/platform-manual.md</code>
                    </li>
                    <li>
                      <strong>Operational single sheet:</strong> <code>docs/studio/essentials.md</code>
                    </li>
                    <li>
                      <strong>GCP + Cloudflare runbook:</strong> <code>docs/studio/deploy-gcp-free-vm.md</code>
                    </li>
                    <li>
                      <strong>Tunnel scripts index:</strong> <code>scripts/studio-cloudflare-tunnel/README.md</code>
                    </li>
                    <li>
                      <strong>Planning index:</strong> <code>docs/studio/README.md</code>
                    </li>
                  </ul>
                </section>

                <p className="docs-footer-note">
                  This page summarizes operator-facing behavior; see the Markdown paths above for versioned detail,
                  examples, and CI. For product vision and roadmap, use <code>docs/studio/vision-and-scope.md</code> and{" "}
                  <code>docs/studio/phased-roadmap.md</code>.
                </p>
              </div>
            </div>
          </article>
        </main>

        <footer className="footer">
          <span>© {new Date().getFullYear()} Immersive Labs</span>
          <span className="footer-meta">
            <Link to="/">Home</Link>
            {" · "}
            <Link to="/studio">Game studio</Link>
          </span>
        </footer>
      </div>
    </>
  );
}

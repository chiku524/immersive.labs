import { useEffect, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { EngravedBackdrop } from "../components/EngravedBackdrop";
import { PrivatePluginDownloadGate } from "../components/PrivatePluginDownloadGate";
import { fabPluginPackageBySlug, fabPluginPackages, fabPluginUrlPath } from "../data/fabPluginPackages";
import "../App.css";
import "./PrivatePluginDownloadPage.css";

const DEFAULT_TITLE = "Immersive Labs — Digital Product Studio";
const NOINDEX = "noindex, nofollow";

function setRobotsNoindex() {
  const existing = document.querySelector("meta[name='robots']");
  if (existing) {
    (existing as HTMLMetaElement).content = NOINDEX;
  } else {
    const m = document.createElement("meta");
    m.name = "robots";
    m.content = NOINDEX;
    document.head.appendChild(m);
  }
}

function NotFound() {
  return (
    <main className="pp-content">
      <h1 className="pp-title" style={{ marginBottom: "0.75rem" }}>
        Not found
      </h1>
      <p className="pp-muted">No plugin page for that URL.</p>
      <p style={{ marginTop: "1.5rem" }}>
        <Link to="/p/plugins">All plugin zips</Link> · <Link to="/fab-products">Fab products</Link>
      </p>
    </main>
  );
}

function SiteChrome({ children }: { children: ReactNode }) {
  return (
    <>
      <EngravedBackdrop />
      <div className="page private-plugin-page">
        <header className="header">
          <Link className="logo" to="/">
            <img className="logo-mark-img" src="/brand-mark.png" alt="" width={32} height={32} />
            Immersive Labs
          </Link>
          <nav className="nav" aria-label="Primary">
            <Link to="/">Home</Link>
            <Link to="/fab-products">Fab products</Link>
            <Link to="/docs">Docs</Link>
            <a href="mailto:nico.builds@outlook.com">Contact</a>
          </nav>
        </header>
        {children}
      </div>
    </>
  );
}

export function PrivatePluginListPage() {
  useEffect(() => {
    setRobotsNoindex();
    document.title = "Private · Fab plugin zips (UE 5.7) · IL";
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, []);

  return (
    <SiteChrome>
      <main className="pp-content">
        <PrivatePluginDownloadGate>
          <h1 className="pp-title">Fab plugin zips (UE 5.7 · Win64)</h1>
          <p className="pp-muted" style={{ maxWidth: "52ch" }}>
            Same RunUAT plugin zips as <Link to="/fab-products">/fab-products</Link>, with one page
            per product. This area can stay unlisted and optionally passphrase-gated; filenames are
            identical to the public download list.
          </p>
          <ul className="pp-list">
            {fabPluginPackages.map((p) => (
              <li key={p.slug}>
                <Link to={`/p/plugins/${p.slug}`}>{p.shortName}</Link>
                <span className="pp-muted"> — {p.name}</span>
              </li>
            ))}
          </ul>
        </PrivatePluginDownloadGate>
      </main>
    </SiteChrome>
  );
}

export function PrivatePluginDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const pkg = slug ? fabPluginPackageBySlug.get(slug) : undefined;

  useEffect(() => {
    setRobotsNoindex();
  }, [slug]);

  useEffect(() => {
    if (pkg) {
      document.title = `Private · ${pkg.shortName} · IL`;
    } else {
      document.title = "Private · Not found · IL";
    }
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, [pkg]);

  if (!pkg) {
    return (
      <SiteChrome>
        <NotFound />
      </SiteChrome>
    );
  }

  const href = fabPluginUrlPath(pkg);

  return (
    <SiteChrome>
      <main className="pp-content">
        <PrivatePluginDownloadGate>
          <p style={{ margin: "0 0 1rem" }}>
            <Link to="/p/plugins">← All plugin zips</Link>
          </p>
          <h1 className="pp-title" style={{ fontSize: "1.5rem" }}>
            {pkg.name}
          </h1>
          <p style={{ lineHeight: 1.65, color: "#c8d4e0" }}>{pkg.description}</p>
          <p className="pp-muted">
            <strong>UE 5.7</strong> · <strong>Win64</strong> · <code className="pp-code">{pkg.zipFile}</code>
          </p>
          <p className="pp-muted" style={{ fontSize: "0.9rem" }}>
            <strong>Root folder in zip</strong>{" "}
            <code className="pp-code">{pkg.packagedRootFolder}/</code>
          </p>
          <p style={{ margin: "1.25rem 0" }}>
            <a href={href} className="btn btn-primary" download={pkg.zipFile}>
              Download {pkg.zipFile}
            </a>
          </p>
          <p className="pp-muted" style={{ fontSize: "0.9rem" }}>
            {pkg.installNote}
          </p>
          <p className="pp-muted" style={{ fontSize: "0.8rem", marginTop: "1.5rem" }}>
            If the link 404s, run <code className="pp-code">sync-fab-plugin-zips-to-web.ps1</code> in this
            repo&rsquo;s <code className="pp-code">scripts</code> to copy zips from the{" "}
            <code className="pp-code">fab-products</code> build into <code className="pp-code">public</code>
            , then rebuild.
          </p>
        </PrivatePluginDownloadGate>
      </main>
    </SiteChrome>
  );
}

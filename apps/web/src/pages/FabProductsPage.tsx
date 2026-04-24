import { Link } from "react-router-dom";
import { EngravedBackdrop } from "../components/EngravedBackdrop";
import { fabPluginPackages, fabPluginUrlPath, MARKETPLACE_ZIP_PREFIX, PLUGIN_ZIP_DIR } from "../data/fabPluginPackages";
import "../App.css";
import "./FabProductsPage.css";

export function FabProductsPage() {
  return (
    <>
      <EngravedBackdrop />
      <div className="page">
        <header className="header">
          <Link className="logo" to="/">
            <img className="logo-mark-img" src="/brand-mark.png" alt="" width={32} height={32} />
            Immersive Labs
          </Link>
          <nav className="nav" aria-label="Primary">
            <Link to="/">Home</Link>
            <a href="#downloads">Downloads</a>
            <Link to="/studio">Game studio</Link>
            <Link to="/docs">Docs</Link>
            <a href="mailto:nico.builds@outlook.com">Contact</a>
          </nav>
        </header>

        <main>
          <section className="hero">
            <p className="eyebrow">Unreal Engine · Fab</p>
            <h1 className="hero-title">
              Product <span className="hero-accent">downloads</span>
            </h1>
            <p className="hero-lede">
              These are <strong>RunUAT packaged plugin</strong> drops—the same <strong>Win64 / UE 5.7</strong> zips
              you upload for Fab. Each download is a single file named{" "}
              <code className="fab-code">{"<Product>-" + MARKETPLACE_ZIP_PREFIX + ".zip"}</code>, matching
              <code className="fab-code"> fab-products/fab-marketplace-drops/UE5.7-Win64/</code> after
              <code className="fab-code"> build-fab-marketplace-drops-ue57.ps1</code>. The archive contains
              one top-level folder (for example <code className="fab-code">HarborSuite-UE5.7-Win64</code>)—
              that is the BuildPlugin output; copy it under your project&rsquo;s <code className="fab-code">Plugins</code>{" "}
              and enable the plugin. These are <strong>not</strong> the optional source-only sample
              <code className="fab-code">.uproject</code> trees (see script note below); there is
              <strong> no</strong> sample project inside these zips, only the packaged plugin.
            </p>
            <p className="fab-rebuild-hint" role="note">
              Site assets: from <code className="fab-code">immersive.labs</code>, run{" "}
              <code className="fab-code">scripts/sync-fab-plugin-zips-to-web.ps1</code> to copy
              <code className="fab-code"> *.zip</code> into <code className="fab-code">apps/web/public/{PLUGIN_ZIP_DIR}/</code>{" "}
              and redeploy. Optional separate archives of full <em>source</em> sample projects (for local use):
              <code className="fab-code"> scripts/package-fab-product-zips.ps1</code> (defaults to
              <code className="fab-code"> public/fab-samples/</code>) after syncing embedded plugins with
              <code className="fab-code"> fab-products/scripts/sync-fab-demo-plugins.ps1</code> when needed.
            </p>
          </section>

          <section id="downloads" className="section">
            <h2 className="section-title">Plugin ZIP downloads (UE 5.7 · Win64)</h2>
            <p className="section-intro">
              Publisher: <strong>Immersive Labs</strong>. <strong>Download</strong> labels match the
              on-disk and Fab filenames exactly.
            </p>
            <ul className="card-grid fab-dl-grid">
              {fabPluginPackages.map((p) => {
                const href = fabPluginUrlPath(p);
                return (
                  <li key={p.slug} className="card fab-dl-card">
                    <span className="card-tag">{p.tag}</span>
                    <h3 className="card-title">{p.shortName}</h3>
                    <p className="card-body">{p.cardBlurb}</p>
                    <p className="fab-dl-uproject">
                      <span className="fab-dl-k">Root folder in zip</span>{" "}
                      <code className="fab-code">{p.packagedRootFolder}/</code>
                    </p>
                    <p className="fab-dl-engine">UE 5.7 · Win64 · {p.zipFile}</p>
                    <a className="btn btn-primary fab-dl-btn" href={href} download={p.zipFile}>
                      Download {p.zipFile}
                    </a>
                  </li>
                );
              })}
            </ul>
          </section>
        </main>

        <footer className="footer">
          <p className="footer-meta">Immersive Labs · Unreal / Fab product drops</p>
          <p className="footer-meta">
            <a href="mailto:nico.builds@outlook.com">nico.builds@outlook.com</a>
          </p>
        </footer>
      </div>
    </>
  );
}

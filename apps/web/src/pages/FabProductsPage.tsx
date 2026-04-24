import { Link } from "react-router-dom";
import { EngravedBackdrop } from "../components/EngravedBackdrop";
import "../App.css";
import "./FabProductsPage.css";

export type FabProductDownload = {
  id: string;
  name: string;
  tag: string;
  blurb: string;
  uproject: string;
  zipFile: string;
  engineNote: string;
};

const DOWNLOADS: FabProductDownload[] = [
  {
    id: "harbor-suite",
    name: "Harbor Suite",
    tag: "Unreal · Editor workflow",
    blurb: "Sample project with Harbor Suite embedded: small-team editor workflow, panels, and runtime hooks.",
    uproject: "Harbor/Harbor.uproject",
    zipFile: "harbor-suite-harbor.zip",
    engineNote: "UE 5.7+ (see product docs for minor line matrix)",
  },
  {
    id: "level-selection-sets",
    name: "Level Selection Sets",
    tag: "Unreal · Editor",
    blurb: "Named actor selection sets per level: recall lighting passes, prop sweeps, and batch edits without losing your place.",
    uproject: "LevelSelectionSetsDemo/LevelSelectionSetsDemo.uproject",
    zipFile: "level-selection-sets-demo.zip",
    engineNote: "UE 5.4+; demo association 5.7",
  },
  {
    id: "worldbuilder-templates",
    name: "World Builder Templates",
    tag: "Unreal · World templates",
    blurb: "Plugin-shipped world maps as starting points: open as a template or load directly from the editor.",
    uproject: "WorldBuilderTemplatesDemo/WorldBuilderTemplatesDemo.uproject",
    zipFile: "worldbuilder-templates-demo.zip",
    engineNote: "UE 5.7+",
  },
  {
    id: "workflow-toolkit",
    name: "Workflow Toolkit",
    tag: "Unreal · Editor + runtime",
    blurb: "Editor shortcuts and a runtime game-instance subsystem for PIE and dev utilities.",
    uproject: "WorkflowToolkitDemo/WorkflowToolkitDemo.uproject",
    zipFile: "workflow-toolkit-demo.zip",
    engineNote: "UE 5.4+; demo association 5.7",
  },
];

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
              Full <strong>sample projects</strong> (same idea as the <strong>Harbor</strong> / Harbor-style
              demos): each zip
              includes a <strong>.uproject</strong>, <strong>Source/</strong>, <strong>Config/</strong>,{" "}
              <strong>Content/</strong> where used, <strong>LICENSE</strong> at the project root, and the
              product source under <strong>Plugins/</strong>. Build outputs are left out of the
              zip—regenerate Visual Studio / project files and build locally after unzip.
            </p>
            <p className="fab-rebuild-hint" role="note">
              To refresh the web zips after Fab repo changes, run{" "}
              <code className="fab-code">scripts/package-fab-product-zips.ps1</code> in immersive.labs, then
              ship <code className="fab-code">public/fab-products/*.zip</code>. If you only updated a
              canonical plugin folder, use <code className="fab-code">fab-products/scripts/sync-fab-demo-plugins.ps1</code> first
              so the embedded <code className="fab-code">Plugins/</code> trees in the demos match.
            </p>
          </section>

          <section id="downloads" className="section">
            <h2 className="section-title">ZIP downloads</h2>
            <p className="section-intro">
              Publisher: <strong>Immersive Labs</strong>. Use these drops for local evaluation and pipeline
              testing alongside Epic Fab listings.
            </p>
            <ul className="card-grid fab-dl-grid">
              {DOWNLOADS.map((p) => (
                <li key={p.id} className="card fab-dl-card">
                  <span className="card-tag">{p.tag}</span>
                  <h3 className="card-title">{p.name}</h3>
                  <p className="card-body">{p.blurb}</p>
                  <p className="fab-dl-uproject">
                    <span className="fab-dl-k">Open</span> {p.uproject}
                  </p>
                  <p className="fab-dl-engine">{p.engineNote}</p>
                  <a
                    className="btn btn-primary fab-dl-btn"
                    href={`/fab-products/${p.zipFile}`}
                    download={p.zipFile}
                  >
                    Download {p.zipFile}
                  </a>
                </li>
              ))}
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

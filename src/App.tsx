import { DigitalProductShowcase } from "./components/DigitalProductShowcase";
import { EngravedBackdrop } from "./components/EngravedBackdrop";
import "./App.css";

export default function App() {
  return (
    <>
      <EngravedBackdrop />
      <div className="page">
        <header className="header">
          <a className="logo" href="/">
            <span className="logo-mark" />
            Immersive Labs
          </a>
          <nav className="nav" aria-label="Primary">
            <a href="#products">Products</a>
            <a href="#work">Work</a>
            <a href="#capabilities">Capabilities</a>
            <a href="#contact">Contact</a>
          </nav>
        </header>

        <main>
          <section className="hero">
            <p className="eyebrow">Digital product studio</p>
            <h1 className="hero-title">
              Products that feel
              <span className="hero-accent"> immersive</span>
            </h1>
            <p className="hero-lede">
              We design and ship software with clarity, motion, and craft—from first prototype to
              production.
            </p>
            <div className="hero-actions">
              <a className="btn btn-primary" href="#contact">
                Start a project
              </a>
              <a className="btn btn-ghost" href="#work">
                View selected work
              </a>
            </div>
          </section>

          <DigitalProductShowcase />

          <section id="work" className="section">
            <h2 className="section-title">Selected work</h2>
            <p className="section-intro">
              Case studies and launches will live here. For now, this is your canvas—swap in real
              projects as they ship.
            </p>
            <ul className="card-grid">
              <li className="card">
                <span className="card-tag">Product</span>
                <h3 className="card-title">Flagship experience</h3>
                <p className="card-body">End-to-end UX, visual system, and frontend implementation.</p>
              </li>
              <li className="card">
                <span className="card-tag">Platform</span>
                <h3 className="card-title">Design systems</h3>
                <p className="card-body">Tokens, components, and documentation your team can run with.</p>
              </li>
              <li className="card">
                <span className="card-tag">Motion</span>
                <h3 className="card-title">Interfaces in motion</h3>
                <p className="card-body">Micro-interactions and narrative motion that guide attention.</p>
              </li>
            </ul>
          </section>

          <section id="capabilities" className="section section-tight">
            <h2 className="section-title">Capabilities</h2>
            <ul className="pill-row">
              <li>Product strategy</li>
              <li>UX &amp; UI design</li>
              <li>Design engineering</li>
              <li>Prototyping</li>
              <li>Frontend architecture</li>
            </ul>
          </section>

          <section id="contact" className="section cta-block">
            <h2 className="section-title">Let&apos;s build</h2>
            <p className="section-intro">
              Tell us what you&apos;re making—we&apos;ll follow up with next steps.
            </p>
            <a className="btn btn-primary btn-lg" href="mailto:hello@immersive.labs">
              hello@immersive.labs
            </a>
          </section>
        </main>

        <footer className="footer">
          <span>© {new Date().getFullYear()} Immersive Labs</span>
          <span className="footer-meta">Studio for digital products</span>
        </footer>
      </div>
    </>
  );
}

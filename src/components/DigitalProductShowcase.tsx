import { useEffect, useRef, type CSSProperties } from "react";
import "./DigitalProductShowcase.css";

export type DigitalProduct = {
  id: string;
  title: string;
  tagline: string;
  category: string;
};

const PRODUCTS: DigitalProduct[] = [
  {
    id: "1",
    title: "Atlas UI Kit",
    tagline: "Tokens, layouts, and motion-ready components.",
    category: "Design system",
  },
  {
    id: "2",
    title: "Pulse Analytics",
    tagline: "Real-time dashboards your team can trust.",
    category: "SaaS",
  },
  {
    id: "3",
    title: "Nimbus Docs",
    tagline: "Collaborative knowledge with zero friction.",
    category: "Productivity",
  },
  {
    id: "4",
    title: "Forge Commerce",
    tagline: "Checkout flows that convert without the noise.",
    category: "E-commerce",
  },
  {
    id: "5",
    title: "Echo Mobile",
    tagline: "Native-feel PWA patterns and gestures.",
    category: "Mobile",
  },
  {
    id: "6",
    title: "Vertex API",
    tagline: "Developer surfaces that read like prose.",
    category: "Platform",
  },
];

const SCROLL_TURNS = 1.15;

export function DigitalProductShowcase() {
  const trackRef = useRef<HTMLDivElement>(null);
  const carouselRef = useRef<HTMLDivElement>(null);
  const reducedMotionRef = useRef(false);

  useEffect(() => {
    reducedMotionRef.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    const track = trackRef.current;
    const carousel = carouselRef.current;
    if (!track || !carousel) return;

    let raf = 0;

    const tick = () => {
      raf = 0;
      if (reducedMotionRef.current) {
        carousel.style.setProperty("--carousel-y", "0deg");
        return;
      }

      const rect = track.getBoundingClientRect();
      const vh = window.innerHeight;
      const scrollRange = Math.max(1, track.offsetHeight - vh);
      const progress = Math.min(1, Math.max(0, -rect.top / scrollRange));
      const degrees = progress * 360 * SCROLL_TURNS;
      carousel.style.setProperty("--carousel-y", `${degrees}deg`);
    };

    const onScrollOrResize = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
    };

    window.addEventListener("scroll", onScrollOrResize, { passive: true });
    window.addEventListener("resize", onScrollOrResize, { passive: true });

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMotionChange = () => {
      reducedMotionRef.current = mq.matches;
      onScrollOrResize();
    };
    mq.addEventListener("change", onMotionChange);

    onScrollOrResize();

    return () => {
      if (raf) cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScrollOrResize);
      window.removeEventListener("resize", onScrollOrResize);
      mq.removeEventListener("change", onMotionChange);
    };
  }, []);

  const count = PRODUCTS.length;
  const step = 360 / count;

  return (
    <section id="products" className="product-showcase" aria-labelledby="products-heading">
      <div className="product-showcase-intro">
        <p className="product-showcase-eyebrow">Digital products</p>
        <h2 id="products-heading" className="product-showcase-title">
          Holographic showcase
        </h2>
        <p className="product-showcase-lede">
          Scroll through this space to orbit the carousel—a full 360° pass of templates, tools, and
          shipped surfaces.
        </p>
      </div>

      <div className="product-showcase-track" ref={trackRef}>
        <div className="product-showcase-sticky">
          <p className="product-showcase-hint" aria-hidden="true">
            Scroll to orbit
          </p>

          <div className="product-showcase-stage">
            <div className="product-showcase-holo-floor" aria-hidden />
            <div className="product-showcase-scene">
              <div className="product-showcase-carousel" ref={carouselRef}>
                {PRODUCTS.map((product, index) => (
                  <article
                    key={product.id}
                    className="product-showcase-card"
                    style={
                      {
                        "--i": index,
                        "--step": `${step}deg`,
                      } as CSSProperties
                    }
                  >
                    <div className="product-showcase-card-inner">
                      <span className="product-showcase-card-scan" aria-hidden />
                      <span className="product-showcase-card-category">{product.category}</span>
                      <h3 className="product-showcase-card-title">{product.title}</h3>
                      <p className="product-showcase-card-tagline">{product.tagline}</p>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

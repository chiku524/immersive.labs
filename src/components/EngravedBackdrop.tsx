import "./EngravedBackdrop.css";

export function EngravedBackdrop() {
  return (
    <div className="backdrop" aria-hidden>
      <div className="ambient" />
      <div className="stone" />
      <div className="grain" />
      <div className="neon-layer">
        <div className="neon neon-orb neon-a" />
        <div className="neon neon-orb neon-b" />
        <div className="neon neon-orb neon-c" />
        <div className="neon neon-arc neon-d" />
        <div className="neon neon-arc neon-e" />
        <div className="neon neon-dash neon-f" />
        <div className="neon neon-dash neon-g" />
        <div className="neon neon-dot neon-h" />
        <div className="neon neon-dot neon-i" />
      </div>
    </div>
  );
}

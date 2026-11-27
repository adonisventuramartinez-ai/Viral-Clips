export default function Loading() {
  const shimmer = { background: "linear-gradient(90deg,#0b1022,#182341,#0b1022)", backgroundSize: "200% 100%", borderRadius: 12 };
  return (
    <div className="page">
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ ...shimmer, height: 28, width: 260, animation: "fadeIn 1s infinite alternate" }} />
        <div style={{ ...shimmer, height: 14, width: 420, maxWidth: "80%", marginTop: 12, animation: "fadeIn 1.2s infinite alternate" }} />
      </div>
      <div className="grid2">
        {[0, 1, 2, 3].map((i) => <div key={i} className="card" style={{ ...shimmer, height: 180, animation: "fadeIn 1s infinite alternate", animationDelay: `${i * 0.15}s` }} />)}
      </div>
    </div>
  );
}

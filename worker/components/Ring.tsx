export default function Ring({ time, label = "EN VIVO" }: { time: string; label?: string }) {
  return (
    <div className="ring">
      <svg viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="44" fill="none" stroke="#ff2d4f" strokeWidth="3" strokeDasharray="60 20" strokeLinecap="round" />
        <circle cx="50" cy="50" r="38" fill="none" stroke="#2ee6d6" strokeWidth="2" strokeDasharray="8 10" />
      </svg>
      <div className="t"><b>{time}</b><i>{label}</i></div>
    </div>
  );
}

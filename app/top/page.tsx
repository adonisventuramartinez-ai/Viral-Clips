"use client";
import CommunityFeed from "@/components/CommunityFeed";

export default function Top() {
  return (
    <>
      <h1>🏆 Top global</h1>
      <p className="sub">Los clips con mayor probabilidad viral de toda la comunidad.</p>
      <div className="card"><CommunityFeed kind="top" limit={30} /></div>
    </>
  );
}

'use client';

import { useEffect, useState } from 'react';

type Commit = {
  sha: string;
  author: string;
  email: string;
  date: string;
  message: string;
  files: number | null;
};

type Feed = { configured: boolean; commits: Commit[]; error?: string };

function timeAgo(iso: string): string {
  const delta = (Date.now() - new Date(iso).getTime()) / 1000;
  if (delta < 60) return `${Math.floor(delta)}s`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h`;
  return `${Math.floor(delta / 86400)}d`;
}

// Colour-code the author dot so the eye can scan Hermes vs Ari in one
// glance. Any third author falls through to the neutral gray.
function authorColor(name: string): string {
  if (name === 'Hermes PA') return '#fb923c'; // amber - matches the accent
  if (name.includes('Birnbaum')) return '#a3b18a'; // sage, borrowed from Company
  return '#707070';
}

// "Hermes: daily 19.04.26 + Person Sandra Habermann" -> "daily 19.04.26 + Person Sandra Habermann"
// Removes the Hermes: prefix that every auto-commit has, since the author
// dot already encodes that.
function cleanMessage(m: string): string {
  return m.replace(/^Hermes:\s*/, '');
}

export default function ActivityFeed(_props: { inline?: boolean } = {}) {
  const [data, setData] = useState<Feed | null>(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch('/api/activity', { cache: 'no-store' });
        const j = (await r.json()) as Feed;
        if (!cancelled) setData(j);
      } catch {
        // leave previous data on error - no flash
      }
    };
    load();
    const t = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  // Tick the "time ago" labels every 15 seconds so they feel alive.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="activity" key={now}>
      <div className="activity-sub">vault git log</div>

      {data == null && <div className="activity-empty">loading</div>}

      {data && !data.configured && (
        <div className="activity-empty">
          set <code>OBSIDIAN_VAULT_GITHUB_TOKEN</code> env var
        </div>
      )}

      {data && data.configured && data.commits.length === 0 && (
        <div className="activity-empty">
          no commits {data.error ? `· ${data.error}` : ''}
        </div>
      )}

      {data && data.commits.map((c) => (
        <div className="activity-row" key={c.sha}>
          <div className="activity-line">
            <span
              className="activity-dot"
              style={{ background: authorColor(c.author) }}
              title={c.author}
            />
            <span className="activity-ago">{timeAgo(c.date)}</span>
            <span className="activity-sha">{c.sha}</span>
          </div>
          <div className="activity-msg" title={c.message}>
            {cleanMessage(c.message)}
          </div>
        </div>
      ))}
    </div>
  );
}

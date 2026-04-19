'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

type Task = {
  id: number;
  name: string;
  status: string;
  priority: string;
  deadline: string | null;
  assignee: string | null;
  area: string | null;
  type: string | null;
  degree: number;
};

type Feed = { tasks: Task[]; error?: string };

// "2026-04-20" -> {label: "tomorrow", overdue: false, today: false, days: 1}
function parseDeadline(iso: string | null) {
  if (!iso) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const d = new Date(iso);
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const days = Math.round((target.getTime() - today.getTime()) / 86_400_000);
  let label: string;
  if (days < 0) label = `${-days}d over`;
  else if (days === 0) label = 'today';
  else if (days === 1) label = 'tomorrow';
  else if (days < 7) label = `in ${days}d`;
  else label = target.toISOString().slice(5, 10).replace('-', '.');
  return { iso, days, label, overdue: days < 0, today: days === 0 };
}

// Sort: overdue-todos -> today-todos -> near-future-todos (by deadline) ->
// undated-todos -> doing -> done at the very bottom.
function sortKey(t: Task): [number, number, number] {
  const statusRank =
    t.status === 'done' ? 3 :
    t.status === 'doing' ? 2 : 1;
  const d = parseDeadline(t.deadline);
  const priorityRank =
    t.priority === 'high' ? 0 :
    t.priority === 'low' ? 2 : 1;
  if (!d) return [statusRank, 999_999, priorityRank];
  return [statusRank, d.days, priorityRank];
}

function statusColor(status: string, priority: string): string {
  if (status === 'done') return '#3a3a3a';
  if (status === 'doing') return '#f4d35e';
  if (priority === 'high') return '#fb923c';
  return '#a3b18a';
}

export default function TaskBoard() {
  const [data, setData] = useState<Feed | null>(null);
  const router = useRouter();
  const params = useSearchParams();
  const selectedId = Number.parseInt(params.get('n') ?? '', 10);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch('/api/tasks', { cache: 'no-store' });
        const j = (await r.json()) as Feed;
        if (!cancelled) setData(j);
      } catch {
        /* keep previous */
      }
    };
    load();
    const t = setInterval(load, 120_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const sorted = useMemo(
    () => (data?.tasks ?? []).slice().sort((a, b) => {
      const ka = sortKey(a);
      const kb = sortKey(b);
      for (let i = 0; i < 3; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
      return a.name.localeCompare(b.name);
    }),
    [data],
  );

  const open = sorted.filter((t) => t.status !== 'done');
  const done = sorted.filter((t) => t.status === 'done');

  const select = (id: number) => {
    const q = new URLSearchParams(params.toString());
    q.set('n', String(id));
    router.replace(`?${q.toString()}`, { scroll: false });
  };

  const renderTask = (t: Task) => {
    const dl = parseDeadline(t.deadline);
    const active = t.id === selectedId;
    return (
      <button
        key={t.id}
        className={`task-card${active ? ' active' : ''}${t.status === 'done' ? ' done' : ''}`}
        onClick={() => select(t.id)}
      >
        <div className="task-top">
          <span
            className="task-pill"
            style={{ background: statusColor(t.status, t.priority) }}
            title={`${t.status} · ${t.priority}`}
          />
          {dl && (
            <span
              className={`task-deadline${dl.overdue ? ' over' : dl.today ? ' today' : ''}`}
            >
              {dl.label}
            </span>
          )}
          {!dl && t.priority === 'high' && (
            <span className="task-deadline prio">hi</span>
          )}
          <span className="task-area">{t.area ?? t.status}</span>
        </div>
        <div className="task-name">{t.name}</div>
      </button>
    );
  };

  return (
    <div className="task-board">
      {data == null && <div className="activity-empty">loading</div>}
      {data && open.length === 0 && done.length === 0 && (
        <div className="activity-empty">no task nodes yet</div>
      )}
      {data?.error && (
        <div className="activity-empty">error · {data.error}</div>
      )}
      {open.length > 0 && (
        <div className="task-group">
          {open.map(renderTask)}
        </div>
      )}
      {done.length > 0 && (
        <>
          <div className="task-group-label">Done <span>{done.length}</span></div>
          <div className="task-group">
            {done.map(renderTask)}
          </div>
        </>
      )}
    </div>
  );
}

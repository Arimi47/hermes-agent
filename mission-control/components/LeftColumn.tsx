'use client';

import { useState } from 'react';
import ActivityFeed from './ActivityFeed';
import TaskBoard from './TaskBoard';

type Tab = 'tasks' | 'activity';

export default function LeftColumn() {
  const [tab, setTab] = useState<Tab>('tasks');
  return (
    <aside className="left-col">
      <div className="left-tabs">
        <button
          className={`left-tab${tab === 'tasks' ? ' active' : ''}`}
          onClick={() => setTab('tasks')}
        >
          Tasks
        </button>
        <button
          className={`left-tab${tab === 'activity' ? ' active' : ''}`}
          onClick={() => setTab('activity')}
        >
          Activity
        </button>
      </div>
      <div className="left-body">
        {tab === 'tasks' ? <TaskBoard /> : <ActivityFeed inline />}
      </div>
    </aside>
  );
}

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Activity, ArrowRight, CheckCircle2, Cpu, Download, MemoryStick, Play, RefreshCw, Search, Server, ShieldAlert, Square, Terminal, Wifi, WifiOff } from 'lucide-react';
import { BrandMark } from './components/BrandMark';
import { StatusTag } from './components/StatusTag';

type ContainerState = { id?: string; status: string; pid?: number | null; error?: string };
type HostEvent = { time: string; message: string; level: string };
type LiveStatus = {
  connected: boolean; reason: string | null; platform: string; source: ContainerState; destination: ContainerState; active_container: string;
  cpu_percent: number | null; memory_mb: number | null;
  config: { cpu_threshold: number; memory_threshold: number; check_interval: number; auto_migrate: boolean };
  controller_authorized: boolean; cgroup_path: string; monitor_running: boolean; migration_active: boolean;
  source_bundle_ready: boolean; destination_bundle_ready: boolean; docker_available: boolean;
  runc_available: boolean; can_operate: boolean; load_running: boolean;
  events: HostEvent[]; timestamp: string;
};

const pages = [['landing', 'Home'], ['workspace', 'Live workspace'], ['activity', 'Activity']] as const;

function Metric({ icon, label, value, foot }: { icon: ReactNode; label: string; value: string; foot: string }) {
  return <article className="metric-tile"><div className="metric-tile__icon metric-tile__icon--cyan">{icon}</div><div className="metric-tile__label">{label}</div><div className="metric-tile__value">{value}</div><div className="metric-tile__foot">{foot}</div></article>;
}

function Landing({ onOpen }: { onOpen: () => void }) {
  return <section className="hero landing" aria-labelledby="hero-title">
    <div className="hero__copy">
      <div className="hero__eyebrow"><span className="pulse-dot" /> INTELLIGENT PROCESS MIGRATION</div>
      <h1 id="hero-title">Move a running process.<br /><span>Keep it moving.</span></h1>
      <p className="hero__lede">Monitor a container’s CPU and memory. When resource pressure crosses the configured threshold, checkpoint the process and restore it in a destination container. Follow the real process and output from one workspace.</p>
      <div className="landing-steps">
        <article><b>01</b><div><strong>Monitor</strong><span>Read live container and cgroup state.</span></div></article>
        <article><b>02</b><div><strong>Checkpoint</strong><span>Save the running process with CRIU.</span></div></article>
        <article><b>03</b><div><strong>Restore</strong><span>Resume with runc and inspect results.</span></div></article>
      </div>
      <div className="hero__actions"><button className="button button--primary" type="button" onClick={onOpen}><Activity size={16} /> Open live workspace <ArrowRight size={15} /></button></div>
      <p className="landing-note">The workspace displays real host readings. It never substitutes sample values for live telemetry.</p>
    </div>
    <div className="landing-visual"><div className="landing-visual__label"><span className="pulse-dot pulse-dot--teal" /> PROCESS LIFECYCLE</div>
      <div className="landing-flow"><div><span>01</span><strong>migration-source</strong><small>Running workload</small></div><i /><div><span>02</span><strong>CRIU checkpoint</strong><small>Saved process state</small></div><i /><div><span>03</span><strong>migration-restored</strong><small>Resumed destination</small></div></div>
      <div className="landing-visual__foot"><span>runc</span><span>cgroup v2</span><span>CRIU</span></div>
    </div>
  </section>;
}

function LiveWorkspace() {
  const [live, setLive] = useState<LiveStatus | null>(null);
  const [bridgeOnline, setBridgeOnline] = useState(false);
  const [bridgeError, setBridgeError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const onlineRef = useRef(false);

  async function refreshStatus() {
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      const contentType = response.headers.get('content-type') ?? '';
      if (!contentType.includes('application/json')) throw new Error(`Live API returned HTTP ${response.status} without JSON. Check that the host bridge is running on port 4174.`);
      const payload = await response.json() as LiveStatus & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? `API returned ${response.status}.`);
      setLive(payload); setBridgeOnline(true); onlineRef.current = true; setBridgeError('');
    } catch (error) {
      setLive(null); setBridgeOnline(false); onlineRef.current = false;
      setBridgeError(error instanceof Error ? error.message : 'Could not connect to the local API bridge.');
    }
  }

  useEffect(() => {
    let mounted = true;
    let timer = 0;
    const poll = async () => { await refreshStatus(); if (mounted) timer = window.setTimeout(poll, onlineRef.current ? 2000 : 6000); };
    void poll();
    return () => { mounted = false; window.clearTimeout(timer); };
  }, []);

  async function postAction(path: string, confirmation?: string) {
    if (confirmation && !window.confirm(confirmation)) return;
    setBusy(true); setNotice('');
    try {
      const response = await fetch(path, { method: 'POST' });
      const payload = await response.json() as { message?: string; error?: string };
      if (!response.ok) throw new Error(payload.error ?? `Action failed (${response.status}).`);
      setNotice(payload.message ?? 'Action completed.'); await refreshStatus();
    } catch (error) { setNotice(error instanceof Error ? error.message : 'The backend action failed.'); }
    finally { setBusy(false); }
  }

  function toggleMonitor() {
    if (!live) return;
    const action = live.monitor_running ? 'stop' : 'start';
    const confirmation = action === 'start'
      ? live.config.auto_migrate
        ? `Start monitoring ${live.source.id ?? 'migration-source'}? At ${live.config.cpu_threshold}% CPU, the configured controller can checkpoint this workload, replace the checkpoint directory, and restore it to the destination.`
        : 'Start the live monitor? Automatic migration is disabled in the project config.'
      : undefined;
    void postAction(`/api/monitor/${action}`, confirmation);
  }

  function runCpuBurst() {
    void postAction('/api/load/start', 'Apply a bounded 12-second CPU burst inside migration-source? This changes its live cgroup CPU usage and may trigger the configured automatic migration.');
  }

  const events = live?.events ?? [];
  const messages = events.map((event) => event.message.toLowerCase()).join(' ');
  const sourceStatus = live?.source.status ?? 'unknown';
  const destinationRunning = live?.destination.status === 'running';
  const thresholdSeen = /migration candidate|threshold.*(cross|exceed)|\[decision\]/i.test(messages);
  const checkpointSeen = /checkpoint/i.test(messages);
  const restoredOutput = events.find((event) => /^\[RESTORE\].*\[WORKLOAD\].*counter=\d+/i.test(event.message));
  const restoredCounter = restoredOutput?.message.match(/counter=(\d+)/i)?.[1];
  const phases = [
    { title: 'Source workload', detail: live ? sourceStatus === 'running' ? `Running · PID ${live.source.pid ?? 'available'}` : destinationRunning ? 'Migrated · source stopped' : sourceStatus : 'Waiting for host data', done: sourceStatus === 'running' || destinationRunning, active: false },
    { title: 'Resource monitor', detail: live?.monitor_running ? `Sampling every ${live.config.check_interval}s` : thresholdSeen || checkpointSeen || destinationRunning ? 'Monitor completed its migration check' : live ? 'Monitor stopped' : 'Waiting for host data', done: Boolean(live?.monitor_running || thresholdSeen || checkpointSeen || destinationRunning), active: Boolean(live?.monitor_running && !live.migration_active) },
    { title: 'Threshold decision', detail: thresholdSeen ? 'Threshold event received' : live ? `Watching CPU · ${live.config.cpu_threshold}%` : 'Waiting for monitor output', done: thresholdSeen, active: Boolean(live?.monitor_running && !thresholdSeen) },
    { title: 'Checkpoint', detail: checkpointSeen ? 'Controller output received' : live ? 'Waiting for trigger' : 'Waiting for monitor output', done: checkpointSeen, active: Boolean(live?.migration_active) },
    { title: 'Destination restore', detail: live ? `${live.destination.status}${live.destination.pid ? ` · PID ${live.destination.pid}` : ''}` : 'Waiting for host data', done: live?.destination.status === 'running', active: Boolean(live?.migration_active && /restore/i.test(messages)) },
    { title: 'Workload continues', detail: restoredCounter ? `Restored counter output · ${restoredCounter}` : destinationRunning ? 'Waiting for restored workload output' : 'Waiting for destination restore', done: Boolean(restoredCounter), active: destinationRunning && !restoredCounter },
  ];

  return <section className="workspace-page" aria-labelledby="workspace-title">
    <header className="workspace-heading"><div><span className="hero__eyebrow"><span className="pulse-dot" /> OPERATE THE PROJECT</span><h1 id="workspace-title">Live migration workspace</h1><p>Operate the monitor, follow each migration stage, and inspect output from the backend in one place.</p></div></header>
    <div className="live-panel" aria-live="polite">
      <div className="live-panel__head"><div className="live-panel__title"><Server size={19} /><div><span className="eyebrow">PROJECT BACKEND</span><h3>Host connection and controls</h3></div></div><StatusTag tone={live?.connected ? 'teal' : 'amber'} dot>{live?.connected ? 'READY' : bridgeOnline ? 'RUNTIME NOT READY' : 'OFFLINE'}</StatusTag></div>
      {!bridgeOnline ? <div className="live-panel__offline"><WifiOff size={21} /><div><strong>Waiting for the Linux host bridge</strong><p>Run the API beside the migration scripts on the Linux machine that runs runc and CRIU.</p><code>sudo -E python3 api/server.py</code><small>{bridgeError || 'Retrying connection…'}</small><button className="button button--quiet" type="button" onClick={() => void refreshStatus()}><RefreshCw size={14} /> Retry connection</button></div></div> : <>
        {!live?.connected && <div className="live-runtime-warning"><ShieldAlert size={18} /><div><strong>The bridge is online, but the runtime is not ready.</strong><p>{live?.reason}</p><code>{live?.cgroup_path}</code></div></div>}
        {live && <>
          <div className="workspace-actions"><div><span className="eyebrow">DEMO CONTROLS</span><strong>Operate the real workload</strong><p>Run each step on the connected Linux host. Output from the workload, monitor, and migration controller appears below.</p></div>
            {!live.source_bundle_ready || !live.destination_bundle_ready ? <button className="button button--quiet" type="button" disabled={busy || !live.can_operate || !live.docker_available} onClick={() => void postAction('/api/runtime/prepare', 'Build the project workload image and export its root filesystem into both runc bundles? This can take a few minutes and uses Docker on the Linux host.')}><RefreshCw size={14} /> {busy ? 'Preparing…' : 'Prepare workload bundles'}</button> : sourceStatus !== 'running' ? <button className="button button--primary" type="button" disabled={busy || !live.can_operate || !live.runc_available || live.destination.status === 'running'} onClick={() => void postAction('/api/container/source/start', 'Start the real migration-source counter workload with runc?')}><Play size={14} fill="currentColor" /> {live.destination.status === 'running' ? 'Reset before replay' : 'Start source workload'}</button> : <button className={live.monitor_running ? 'button button--secondary' : 'button button--primary'} type="button" onClick={toggleMonitor} disabled={busy || !live.connected || live.migration_active || (live.config.auto_migrate && !live.controller_authorized)}>{live.monitor_running ? <Square size={14} /> : <Activity size={14} />}{busy ? 'Working…' : live.monitor_running ? live.migration_active ? 'Migration in progress' : 'Stop monitoring' : 'Start monitoring'}</button>}
            <button className="button button--quiet" type="button" onClick={runCpuBurst} disabled={busy || !live.can_operate || sourceStatus !== 'running' || !live.monitor_running || live.load_running || live.migration_active}>{live.load_running ? <Activity size={14} /> : <Cpu size={14} />}{live.load_running ? 'CPU burst running…' : 'Apply 12-second CPU burst'}</button>
            <button className="button button--quiet" type="button" onClick={() => void postAction('/api/demo/reset', 'Stop and remove the migration source and destination containers to reset this demo?')} disabled={busy || !live.can_operate || live.migration_active}><RefreshCw size={14} /> Reset demo</button>
            {(!live.can_operate || ((!live.source_bundle_ready || !live.destination_bundle_ready) && !live.docker_available)) && <small className="workspace-actions__hint">{!live.can_operate ? 'Full demo controls require the Linux API bridge running as root.' : 'Docker is required to prepare the missing workload bundles.'}</small>}
          </div>
          <div className="live-panel__containers"><div><span>SOURCE WORKLOAD</span><strong>{live.source.id ?? 'migration-source'}</strong><StatusTag tone={sourceStatus === 'running' ? 'teal' : 'amber'}>{sourceStatus.toUpperCase()}</StatusTag>{live.source.pid && <small>PID {live.source.pid}</small>}</div><ArrowRight size={18} /><div><span>DESTINATION</span><strong>{live.destination.id ?? 'migration-restored'}</strong><StatusTag tone={live.destination.status === 'running' ? 'teal' : 'muted'}>{live.destination.status.toUpperCase()}</StatusTag>{live.destination.pid && <small>PID {live.destination.pid}</small>}</div></div>
          <div className="live-panel__metrics"><Metric icon={<Cpu size={17} />} label="Active container CPU" value={live.cpu_percent === null ? 'Sampling…' : `${live.cpu_percent}%`} foot={`Threshold · ${live.config.cpu_threshold}%`} /><Metric icon={<MemoryStick size={17} />} label="Active container memory" value={live.memory_mb === null ? 'Unavailable' : `${live.memory_mb.toFixed(1)} MB`} foot={`cgroup memory.current · ${live.active_container}`} /><Metric icon={<Activity size={17} />} label="Monitor" value={live.monitor_running ? 'Running' : 'Stopped'} foot={`Checks every ${live.config.check_interval} seconds`} /></div>
          <div className="live-panel__controls"><button className="button button--quiet" type="button" onClick={() => void refreshStatus()}><RefreshCw size={14} /> Refresh data</button><span><Wifi size={14} /> Refreshes every 2 seconds</span></div>
        </>}
      </>}
      {notice && <p className="live-panel__notice" role="status">{notice}</p>}
      <section className="migration-progress"><div className="workspace-subhead"><div><span className="eyebrow">LIVE PROCESS</span><h3>Migration progress</h3></div><span>Derived from host state and backend events</span></div><ol>{phases.map((phase, index) => <li key={phase.title} className={phase.done ? 'is-done' : phase.active ? 'is-active' : ''}><span className="migration-progress__number">{phase.done ? <CheckCircle2 size={17} /> : String(index + 1).padStart(2, '0')}</span><div><strong>{phase.title}</strong><small>{phase.detail}</small></div>{index < phases.length - 1 && <ArrowRight size={15} className="migration-progress__arrow" />}</li>)}</ol></section>
      <section className="backend-output"><div className="workspace-subhead"><div><span className="eyebrow">BACKEND OUTPUT</span><h3>Host events</h3></div><span>{bridgeOnline ? `${events.length} events · newest first` : 'Waiting for host connection'}</span></div>{events.length ? <ol>{events.map((event, index) => <li key={`${event.time}:${index}`}><time>{event.time}</time><span className={`live-event live-event--${event.level}`}>{event.message}</span></li>)}</ol> : <div className="backend-output__empty"><Terminal size={20} /><p>{bridgeOnline ? 'No monitor output yet. Start monitoring to display live samples and controller messages.' : 'Host output will appear here when the Linux bridge connects.'}</p></div>}</section>
    </div>
  </section>;
}

function ActivityPage() {
  const [events, setEvents] = useState<HostEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [updatedAt, setUpdatedAt] = useState('');

  useEffect(() => {
    let mounted = true;
    let timer = 0;
    const poll = async () => {
      try {
        const response = await fetch('/api/status', { cache: 'no-store' });
        if (!response.ok) throw new Error('Host API is unavailable.');
        const status = await response.json() as LiveStatus;
        if (mounted) { setEvents(status.events ?? []); setConnected(true); setUpdatedAt(new Date().toLocaleTimeString()); }
      } catch {
        if (mounted) { setEvents([]); setConnected(false); }
      }
      if (mounted) timer = window.setTimeout(poll, connected ? 2000 : 6000);
    };
    void poll();
    return () => { mounted = false; window.clearTimeout(timer); };
  }, [connected]);

  function category(event: HostEvent) {
    const text = event.message.toLowerCase();
    if (text.includes('[workload]') || text.includes('[restore]')) return 'workload';
    if (text.includes('[monitor]') || text.includes('[load]') || text.includes('cpu=')) return 'monitor';
    if (text.includes('migration') || text.includes('checkpoint') || text.includes('restore') || text.includes('[decision]') || text.includes('[action]')) return 'migration';
    return 'system';
  }

  const visibleEvents = events.filter((event) => (filter === 'all' || category(event) === filter) && (!query || event.message.toLowerCase().includes(query.toLowerCase())));
  function exportEvents() {
    const contents = visibleEvents.map((event) => `${event.time} [${event.level.toUpperCase()}] ${event.message}`).join('\n');
    const url = URL.createObjectURL(new Blob([contents], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'intelligent-process-migration-activity.txt'; link.click(); URL.revokeObjectURL(url);
  }

  const counts = { workload: events.filter((event) => category(event) === 'workload').length, monitor: events.filter((event) => category(event) === 'monitor').length, migration: events.filter((event) => category(event) === 'migration').length, errors: events.filter((event) => event.level === 'error').length };
  return <section className="activity-page" aria-labelledby="activity-title">
    <header className="workspace-heading"><div><span className="hero__eyebrow"><span className="pulse-dot" /> DEMO RECORD</span><h1 id="activity-title">Activity</h1><p>Review the real output produced by the workload, resource monitor, and migration controller.</p></div><StatusTag tone={connected ? 'teal' : 'amber'} dot>{connected ? 'LIVE EVENT STREAM' : 'HOST OFFLINE'}</StatusTag></header>
    <div className="activity-summary"><article><strong>{counts.workload}</strong><span>Workload lines</span></article><article><strong>{counts.monitor}</strong><span>Resource samples</span></article><article><strong>{counts.migration}</strong><span>Migration events</span></article><article><strong>{counts.errors}</strong><span>Errors</span></article></div>
    <section className="activity-console"><div className="activity-console__head"><div><span className="eyebrow">BACKEND EVENT STREAM</span><h2>Run output</h2></div><div className="activity-console__actions"><span>{updatedAt ? `Updated ${updatedAt}` : connected ? 'Waiting for output' : 'Waiting for Linux host'}</span><button className="button button--quiet" type="button" onClick={exportEvents} disabled={!visibleEvents.length}><Download size={14} /> Export visible events</button></div></div>
      <div className="activity-toolbar"><label className="activity-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search backend output" aria-label="Search backend output" /></label><div className="activity-filters" aria-label="Filter events">{[['all','All'],['workload','Workload'],['monitor','Monitor'],['migration','Migration'],['system','System']].map(([id,label]) => <button key={id} type="button" className={filter === id ? 'activity-filter activity-filter--active' : 'activity-filter'} onClick={() => setFilter(id)}>{label}</button>)}</div></div>
      {visibleEvents.length ? <ol className="activity-list">{visibleEvents.map((event, index) => <li key={`${event.time}:${index}`} className={`activity-row activity-row--${event.level}`}><time>{event.time}</time><StatusTag tone={event.level === 'error' ? 'amber' : category(event) === 'workload' ? 'teal' : category(event) === 'migration' ? 'cyan' : 'muted'}>{category(event).toUpperCase()}</StatusTag><p>{event.message}</p></li>)}</ol> : <div className="activity-empty"><Terminal size={24} /><strong>{connected ? query || filter !== 'all' ? 'No matching events' : 'No backend output yet' : 'Connect the Linux host to begin'}</strong><p>{connected ? query || filter !== 'all' ? 'Try a different search or event filter.' : 'Start the workload and monitor from Live workspace. The backend event stream will appear here.' : 'This view reads only real backend events. It will populate when the Linux API bridge connects.'}</p></div>}
      <div className="activity-console__foot"><span>{visibleEvents.length} of {events.length} events</span><span>Newest events arrive automatically</span></div>
    </section>
  </section>;
}

export default function App() {
  const [page, setPage] = useState<'landing' | 'workspace' | 'activity'>('landing');
  function openPage(next: 'landing' | 'workspace' | 'activity') { setPage(next); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  return <div className="site-shell"><a className="skip-link" href="#main-content">Skip to content</a><header className="topbar">
    <button className="brand" type="button" onClick={() => openPage('landing')} aria-label="Intelligent Process Migration home"><BrandMark /><span className="brand__text">INTELLIGENT<br />PROCESS MIGRATION</span></button>
    <nav className="main-nav" aria-label="Main navigation">{pages.map(([id, label]) => <button key={id} type="button" className={page === id ? 'main-nav__link main-nav__link--active' : 'main-nav__link'} onClick={() => openPage(id)} aria-current={page === id ? 'page' : undefined}>{label}</button>)}</nav>
    <span className="topbar__project"><span className="pulse-dot" /> PROJECT</span>
  </header><main id="main-content" className="page-view" key={page}>{page === 'landing' ? <Landing onOpen={() => openPage('workspace')} /> : page === 'workspace' ? <LiveWorkspace /> : <ActivityPage />}</main></div>;
}

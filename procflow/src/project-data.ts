export const REPOSITORY_URL = 'https://github.com/dhruvil-shah28/intelligent-process-migration';

export type SourceRef = {
  path: string;
  line: number;
  summary: string;
};

export type Stage = {
  number: string;
  title: string;
  short: string;
  detail: string;
  status: 'implemented' | 'configured' | 'documented' | 'simulation';
  sources: SourceRef[];
};

export const stages: Stage[] = [
  {
    number: '01', title: 'Source workload', short: 'runc container',
    detail: 'A persistent Python process increments a counter once per second and emits a line every ten counts.',
    status: 'implemented', sources: [{ path: 'workloads/workload.py', line: 10, summary: 'Counter increment loop' }],
  },
  {
    number: '02', title: 'Resource sampling', short: 'cgroup v2',
    detail: 'The monitor samples cumulative cpu.stat usage_usec and memory.current, calculating CPU from deltas over elapsed time.',
    status: 'implemented', sources: [{ path: 'monitor/cgroup-monitor.sh', line: 38, summary: 'cgroup v2 sampler' }],
  },
  {
    number: '03', title: 'Threshold decision', short: 'CPU ≥ 50%',
    detail: 'The configured cgroup path compares CPU percent with CPU_THRESHOLD. A crossing becomes a MIGRATION CANDIDATE.',
    status: 'configured', sources: [{ path: 'monitor/config.conf', line: 1, summary: 'Thresholds and interval' }],
  },
  {
    number: '04', title: 'Migration trigger', short: 'AUTO_MIGRATE',
    detail: 'When automatic migration is enabled, the cgroup monitor invokes the shell controller and ends its monitoring loop.',
    status: 'implemented', sources: [{ path: 'monitor/cgroup-monitor.sh', line: 66, summary: 'Trigger branch' }],
  },
  {
    number: '05', title: 'CRIU checkpoint', short: 'runc checkpoint',
    detail: 'The controller validates the source, prepares checkpoint directories, and calls runc checkpoint with image and work paths.',
    status: 'implemented', sources: [{ path: 'controller/migrate.sh', line: 41, summary: 'runc checkpoint call' }],
  },
  {
    number: '06', title: 'Destination restore', short: 'runc restore',
    detail: 'The saved images and destination OCI bundle are passed to runc restore; the script then checks the destination state.',
    status: 'implemented', sources: [{ path: 'controller/migrate.sh', line: 49, summary: 'runc restore call' }],
  },
  {
    number: '07', title: 'Continuity check', short: 'Counter resumes',
    detail: 'The demo script inspects source/destination status and workload output. The README reports a final run with the counter continuing after restore.',
    status: 'documented', sources: [{ path: 'demo/run-demo.sh', line: 60, summary: 'Destination workload output check' }, { path: 'README.md', line: 85, summary: 'Reported result' }],
  },
];

export const components: Array<{
  name: string; role: string; status: string; tone: 'cyan' | 'amber' | 'teal' | 'muted';
  sources: SourceRef[];
}> = [
  { name: 'Counter workload', role: 'Long-running Python process; increments an in-memory counter every second.', status: 'Code present', tone: 'cyan', sources: [{ path: 'workloads/workload.py', line: 10, summary: 'Counter increment loop' }, { path: 'migration/workloads/stress_workload.py', line: 8, summary: 'CPU stress example' }] },
  { name: 'cgroup monitor', role: 'Reads cpu.stat and memory.current from a configurable cgroup v2 path; reports CPU and memory MB.', status: 'Code present', tone: 'cyan', sources: [{ path: 'monitor/cgroup-monitor.sh', line: 6, summary: 'Monitor path and sampling' }] },
  { name: 'Threshold config', role: 'CPU 50%, memory 70%, sampling every 2 seconds, automatic migration enabled.', status: 'Configured', tone: 'amber', sources: [{ path: 'monitor/config.conf', line: 1, summary: 'Current configuration' }] },
  { name: 'Migration controller', role: 'Checks source state, prepares paths, checkpoints with runc/CRIU, restores to the destination OCI bundle, and validates state.', status: 'Code present', tone: 'teal', sources: [{ path: 'controller/migrate.sh', line: 25, summary: 'Source validation' }, { path: 'controller/migrate.sh', line: 41, summary: 'Checkpoint call' }, { path: 'controller/migrate.sh', line: 49, summary: 'Restore call' }] },
  { name: 'Demo verifier', role: 'Checks source/destination states and reads the workload output stream; no raw run log is committed.', status: 'Evidence script', tone: 'teal', sources: [{ path: 'demo/run-demo.sh', line: 20, summary: 'runc state checks' }, { path: 'demo/run-demo.sh', line: 60, summary: 'Destination workload output' }] },
  { name: 'Local API bridge', role: 'Connects the browser to live runc state, cgroup readings, and the existing automatic monitor on the Linux host.', status: 'Code present', tone: 'teal', sources: [{ path: 'procflow/api/server.py', line: 1, summary: 'Local API bridge' }] },
  { name: 'Distributed modules', role: 'Separate Python code includes weighted pressure scoring, persistence, node status agents, node selection and checkpoint archive transfer.', status: 'Experimental code path', tone: 'muted', sources: [{ path: 'migration/controller/decision.py', line: 8, summary: 'Pressure scoring' }, { path: 'migration/controller/engine.py', line: 74, summary: 'Persistence configuration' }, { path: 'migration/controller/engine.py', line: 83, summary: 'DRY_RUN mode' }, { path: 'migration/agent/node_agent.py', line: 16, summary: 'Node agent' }, { path: 'migration/agent/transfer.py', line: 52, summary: 'Archive transfer' }] },
];

export const demoSteps = [
  { title: 'Workload running', text: 'The counter process is active in the source container.', cpu: 28, memory: 124, node: 'migration-source', kind: 'normal' },
  { title: 'Metrics sampled', text: 'cgroup v2 usage deltas are sampled at the configured interval.', cpu: 42, memory: 126, node: 'migration-source', kind: 'normal' },
  { title: 'Threshold crossed', text: 'Sample CPU exceeds the configured 50% trigger threshold.', cpu: 78, memory: 128, node: 'migration-source', kind: 'warning' },
  { title: 'Migration triggered', text: 'AUTO_MIGRATE=true routes the candidate to controller/migrate.sh.', cpu: 88, memory: 129, node: 'migration-source', kind: 'warning' },
  { title: 'CRIU checkpoint', text: 'runc checkpoint captures the source process state into the checkpoint path.', cpu: 91, memory: 130, node: 'checkpoint', kind: 'warning' },
  { title: 'runc restore', text: 'The destination OCI bundle starts from the saved checkpoint images.', cpu: 34, memory: 127, node: 'migration-restored', kind: 'success' },
  { title: 'Continuity verified', text: 'The sample counter resumes at the destination; this is illustrative UI state, not a live process.', cpu: 29, memory: 126, node: 'migration-restored', kind: 'success' },
] as const;

export function sourceUrl(path: string, line: number): string {
  return `${REPOSITORY_URL}/blob/main/${path}#L${line}`;
}

export function sourceLabel(source: SourceRef): string {
  return `${source.path}:${source.line}`;
}

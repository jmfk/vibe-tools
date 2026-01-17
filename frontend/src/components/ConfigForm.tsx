import React, { useMemo, useState, useEffect } from 'react';
import { 
  Settings, 
  Cpu, 
  ShieldCheck, 
  Zap, 
  Network, 
  Activity, 
  Database,
  Cloud,
  Layers,
  Repeat,
  Play,
  Square,
  RefreshCw,
  Terminal,
  FileText,
  X,
  Search
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import Ansi from 'ansi-to-react';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- Default Configuration ---
export const DEFAULT_CONFIG = {
  ralph: {
    review: true,
    tests: true,
    coverage: true,
    auto_merge: false,
    include_html_logs: true,
    automerge_branch: "main",
    no_branch_switch: true,
    fast: true
  },
  default_budget: 5.0,
  verbose: false,
  no_branch_switch: false,
  code_editor: "cursor",
  md_editor: "cursor",
  coverage_targets: {
    backend: 85,
    frontend: 85,
    tauri: 85,
    infra: 85
  },
  google_sheet_id: "",
  use_google_sheets: false,
  iterations: {
    implementation: 10,
    debug: 5,
    coverage: 5,
    test_fix: 10,
    prd_interview: 8
  },
  agent: {
    agent: "cursor-agent",
    force: true,
    stream: true
  },
  setup: {
    standalone: true,
    deps_branch_enabled: false
  },
  staging: {
    namespace: "vibe-staging",
    environment: "local"
  },
  services: {
    postgres: {
      host: "localhost",
      port: 5432,
      user: "postgres",
      password: "postgres",
      database: "vibe-tools"
    },
    redis: {
      host: "localhost",
      port: 6379
    }
  }
};

interface ConfigFormProps {
  config: any;
  onChange: (newConfig: any) => void;
  accentColor: string;
}

const Section = ({ title, icon: Icon, children, accentColor }: { title: string, icon: any, children: React.ReactNode, accentColor: string }) => (
  <div className="space-y-4">
    <div className="flex items-center gap-2 pb-2 border-b border-zinc-800/50">
      <Icon size={16} style={{ color: accentColor }} />
      <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">{title}</h3>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {children}
    </div>
  </div>
);

const Field = ({ 
  label, 
  description, 
  children,
  isOverride
}: { 
  label: string, 
  description?: string, 
  children: React.ReactNode,
  isOverride?: boolean
}) => (
  <div className="space-y-1.5">
    <div className="flex items-center justify-between">
      <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-2">
        {label}
        {isOverride && (
          <span className="text-[8px] bg-blue-500/10 text-blue-400 px-1 rounded border border-blue-500/20">Override</span>
        )}
      </label>
    </div>
    {children}
    {description && <p className="text-[10px] text-zinc-600 leading-relaxed">{description}</p>}
  </div>
);

const Switch = ({ checked, onChange, accentColor }: { checked: boolean, onChange: (v: boolean) => void, accentColor: string }) => (
  <button
    onClick={() => onChange(!checked)}
    className={cn(
      "w-8 h-4 rounded-full relative transition-colors duration-200",
      checked ? "bg-blue-600" : "bg-zinc-800"
    )}
    style={checked ? { backgroundColor: accentColor } : {}}
  >
    <div className={cn(
      "absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200",
      checked ? "translate-x-4" : "translate-x-0"
    )} />
  </button>
);

const Input = ({ value, onChange, type = "text" }: { value: any, onChange: (v: any) => void, type?: string }) => (
  <input
    type={type}
    value={value ?? ""}
    onChange={(e) => onChange(type === "number" ? parseFloat(e.target.value) : e.target.value)}
    className="w-full bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-700 transition-all"
  />
);

const ServiceLogOverlay = ({ 
  service, 
  onClose, 
  accentColor,
  onAction 
}: { 
  service: any, 
  onClose: () => void, 
  accentColor: string,
  onAction: (action: string) => void 
}) => {
  const [logs, setLogs] = useState<string[]>([]);
  const logQueue = useRef<string[]>([]);
  const flushTimer = useRef<any>(null);
  const isRunning = service.status === 'running';
  
  useEffect(() => {
    if (!isRunning) return;

    // Start tailing logs via vibe command
    invoke('run_vibe_command', { 
      command: 'servers', 
      args: ['logs', service.name, '-f'] 
    }).catch(console.error);

    const flushLogs = () => {
      if (logQueue.current.length > 0) {
        const toAdd = [...logQueue.current];
        logQueue.current = [];
        setLogs(prev => [...prev, ...toAdd].slice(-500));
      }
      flushTimer.current = null;
    };

    const unlisten = listen('log-line', (event: any) => {
      logQueue.current.push(event.payload as string);
      if (!flushTimer.current) {
        flushTimer.current = setTimeout(flushLogs, 100);
      }
    });

    return () => {
      unlisten.then(f => f());
      if (flushTimer.current) clearTimeout(flushTimer.current);
    };
  }, [service.name, isRunning]);

  return (
    <div className="fixed inset-0 z-[100] bg-zinc-950/90 backdrop-blur-md flex flex-col p-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-zinc-900 border border-zinc-800">
            <Terminal size={20} style={{ color: accentColor }} />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
              {service.name} Logs
              <span className={cn(
                "text-[10px] px-2 py-0.5 rounded-full uppercase tracking-widest border",
                service.status === 'running' ? "bg-green-500/10 text-green-400 border-green-500/20" : 
                service.status === 'not_created' ? "bg-zinc-500/10 text-zinc-400 border-zinc-500/20" :
                "bg-red-500/10 text-red-400 border-red-500/20"
              )}>
                {service.status.replace('_', ' ')}
              </span>
            </h2>
            <p className="text-zinc-500 text-xs mt-1">{service.description}</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={() => onAction('start')}
            className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-green-400 hover:border-green-500/30 transition-all"
            title="Start"
          >
            <Play size={18} />
          </button>
          <button 
            onClick={() => onAction('stop')}
            className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-red-400 hover:border-red-500/30 transition-all"
            title="Stop"
          >
            <Square size={18} />
          </button>
          <button 
            onClick={() => onAction('restart')}
            className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-blue-400 hover:border-blue-500/30 transition-all"
            title="Restart"
          >
            <RefreshCw size={18} />
          </button>
          <div className="w-px h-8 bg-zinc-800 mx-2" />
          <button 
            onClick={onClose}
            className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white transition-all"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="flex-1 bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden flex flex-col">
        <div className="bg-zinc-900/50 px-4 py-2 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500">
            <Activity size={12} />
            LIVE_OUTPUT_STREAM
          </div>
          <button 
            onClick={() => setLogs([])}
            className="text-[10px] font-bold uppercase text-zinc-600 hover:text-zinc-400 transition-colors"
          >
            Clear Buffer
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6 font-mono text-xs scrollbar-thin">
          {logs.map((line, i) => (
            <div key={i} className="mb-0.5 whitespace-pre-wrap break-all">
              <Ansi>{line}</Ansi>
            </div>
          ))}
          {logs.length === 0 && (
            <div className="h-full flex items-center justify-center text-zinc-700 italic">
              Waiting for log output...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const ConfigForm: React.FC<ConfigFormProps> = ({ config, onChange, accentColor }) => {
  const [servers, setServers] = useState<any[]>([]);
  const [loadingServers, setLoadingServers] = useState(false);
  const [activeLogService, setActiveLogOverlay] = useState<any>(null);

  const fetchServers = async () => {
    setLoadingServers(true);
    try {
      const results = await invoke<any[]>('run_vibe_command_json', { 
        command: 'servers', 
        args: ['list', '--json'] 
      });
      // Ensure results is an array
      if (Array.isArray(results)) {
        setServers(results);
      } else {
        console.error("Servers list is not an array:", results);
        setServers([]);
      }
    } catch (e) {
      console.error("Error fetching servers:", e);
      setServers([]);
    } finally {
      setLoadingServers(false);
    }
  };

  useEffect(() => {
    fetchServers();
  }, []);

  const handleServerAction = async (serviceName: string, action: string) => {
    try {
      await invoke('run_vibe_command', { 
        command: 'servers', 
        args: [action, serviceName] 
      });
      // Refresh status after a short delay
      setTimeout(fetchServers, 1000);
    } catch (e) {
      alert(`Error running ${action} on ${serviceName}: ${e}`);
    }
  };

  const handleAutoFill = async (serviceName: string) => {
    try {
      const runningConfig = await invoke<any>('run_vibe_command_json', { 
        command: 'servers', 
        args: ['get-config', serviceName, '--json'] 
      });
      
      if (runningConfig.error) {
        alert(runningConfig.error);
        return;
      }

      // Map service name to config key (some differences exist like s3-linode vs minio-linode)
      let configKey = serviceName;
      if (serviceName === 'minio-linode') configKey = 'postgres'; // Wait, I need to check mappings
      
      // Let's just use the name for now, or match existing
      const keyMap: Record<string, string> = {
        'postgres': 'postgres',
        'redis': 'redis',
        'rabbitmq': 'rabbitmq',
        'mailhog': 'mailhog',
        'minio-linode': 'postgres' // This seems wrong in my previous logic, let's fix it
      };
      
      // Actually let's just use the name if it exists in services
      const currentServices = { ...(config.services || {}) };
      currentServices[serviceName] = {
        ...(currentServices[serviceName] || {}),
        host: runningConfig.host,
        port: runningConfig.port,
        user: runningConfig.user,
        password: runningConfig.password,
        database: runningConfig.database,
        access_key: runningConfig.access_key,
        secret_key: runningConfig.secret_key
      };
      
      onChange({ ...config, services: currentServices });
    } catch (e) {
      alert(`Error auto-filling ${serviceName}: ${e}`);
    }
  };
  const handleChange = (path: string, value: any) => {
    const newConfig = { ...config };
    const parts = path.split('.');
    let current = newConfig;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) current[parts[i]] = {};
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;
    onChange(newConfig);
  };

  const isOverride = (path: string) => {
    const parts = path.split('.');
    let current: any = config;
    let def: any = DEFAULT_CONFIG;
    for (const part of parts) {
      if (current === undefined || current[part] === undefined) return false;
      current = current[part];
      def = def[part];
    }
    return JSON.stringify(current) !== JSON.stringify(def);
  };

  const getVal = (path: string) => {
    const parts = path.split('.');
    let current: any = config;
    let def: any = DEFAULT_CONFIG;
    for (const part of parts) {
      if (current !== undefined) current = current[part];
      if (def !== undefined) def = def[part];
    }
    return current !== undefined ? current : def;
  };

  return (
    <div className="space-y-10 py-4">
      <Section title="Ralph (AI Assistant)" icon={Cpu} accentColor={accentColor}>
        <Field label="Auto Review" description="Ralph will automatically review code changes." isOverride={isOverride('ralph.review')}>
          <Switch checked={getVal('ralph.review')} onChange={(v) => handleChange('ralph.review', v)} accentColor={accentColor} />
        </Field>
        <Field label="Auto Tests" description="Ralph will run tests before committing." isOverride={isOverride('ralph.tests')}>
          <Switch checked={getVal('ralph.tests')} onChange={(v) => handleChange('ralph.tests', v)} accentColor={accentColor} />
        </Field>
        <Field label="Check Coverage" description="Ralph will ensure coverage targets are met." isOverride={isOverride('ralph.coverage')}>
          <Switch checked={getVal('ralph.coverage')} onChange={(v) => handleChange('ralph.coverage', v)} accentColor={accentColor} />
        </Field>
        <Field label="Auto Merge" description="Automatically merge successful PRs." isOverride={isOverride('ralph.auto_merge')}>
          <Switch checked={getVal('ralph.auto_merge')} onChange={(v) => handleChange('ralph.auto_merge', v)} accentColor={accentColor} />
        </Field>
        <Field label="Merge Branch" description="The target branch for auto-merging." isOverride={isOverride('ralph.automerge_branch')}>
          <Input value={getVal('ralph.automerge_branch')} onChange={(v) => handleChange('ralph.automerge_branch', v)} />
        </Field>
        <Field label="Include HTML Logs" description="Generate and include HTML logs in artifacts." isOverride={isOverride('ralph.include_html_logs')}>
          <Switch checked={getVal('ralph.include_html_logs')} onChange={(v) => handleChange('ralph.include_html_logs', v)} accentColor={accentColor} />
        </Field>
        <Field label="No Branch Switch" description="Prevent Ralph from switching branches automatically." isOverride={isOverride('ralph.no_branch_switch')}>
          <Switch checked={getVal('ralph.no_branch_switch')} onChange={(v) => handleChange('ralph.no_branch_switch', v)} accentColor={accentColor} />
        </Field>
        <Field label="Fast Mode" description="Reduce wait times for agent responses." isOverride={isOverride('ralph.fast')}>
          <Switch checked={getVal('ralph.fast')} onChange={(v) => handleChange('ralph.fast', v)} accentColor={accentColor} />
        </Field>
      </Section>

      <Section title="Agent & Editor Settings" icon={ShieldCheck} accentColor={accentColor}>
        <Field label="Agent Type" description="The AI engine to use for task execution." isOverride={isOverride('agent.agent')}>
          <Input value={getVal('agent.agent')} onChange={(v) => handleChange('agent.agent', v)} />
        </Field>
        <Field label="Force Execution" description="Force agents to proceed even with warnings." isOverride={isOverride('agent.force')}>
          <Switch checked={getVal('agent.force')} onChange={(v) => handleChange('agent.force', v)} accentColor={accentColor} />
        </Field>
        <Field label="Stream Output" description="Show agent thoughts and output in real-time." isOverride={isOverride('agent.stream')}>
          <Switch checked={getVal('agent.stream')} onChange={(v) => handleChange('agent.stream', v)} accentColor={accentColor} />
        </Field>
        <Field label="Code Editor" description="Command to open code files (e.g. 'code', 'cursor')." isOverride={isOverride('code_editor')}>
          <Input value={getVal('code_editor')} onChange={(v) => handleChange('code_editor', v)} />
        </Field>
        <Field label="Markdown Editor" description="Command to open markdown files." isOverride={isOverride('md_editor')}>
          <Input value={getVal('md_editor')} onChange={(v) => handleChange('md_editor', v)} />
        </Field>
      </Section>

      <Section title="Budget & Limits" icon={Zap} accentColor={accentColor}>
        <Field label="Default Budget ($)" description="The maximum USD allowed per task." isOverride={isOverride('default_budget')}>
          <Input type="number" value={getVal('default_budget')} onChange={(v) => handleChange('default_budget', v)} />
        </Field>
        <Field label="Verbose Logging" description="Enable detailed debug information." isOverride={isOverride('verbose')}>
          <Switch checked={getVal('verbose')} onChange={(v) => handleChange('verbose', v)} accentColor={accentColor} />
        </Field>
        <Field label="Global No Branch Switch" description="System-wide branch switching prevention." isOverride={isOverride('no_branch_switch')}>
          <Switch checked={getVal('no_branch_switch')} onChange={(v) => handleChange('no_branch_switch', v)} accentColor={accentColor} />
        </Field>
      </Section>

      <Section title="Environment & Setup" icon={Layers} accentColor={accentColor}>
        <Field label="Standalone Mode" description="Run services locally without external dependencies." isOverride={isOverride('setup.standalone')}>
          <Switch checked={getVal('setup.standalone')} onChange={(v) => handleChange('setup.standalone', v)} accentColor={accentColor} />
        </Field>
        <Field label="Deps Branch" description="Use dedicated branches for dependency updates." isOverride={isOverride('setup.deps_branch_enabled')}>
          <Switch checked={getVal('setup.deps_branch_enabled')} onChange={(v) => handleChange('setup.deps_branch_enabled', v)} accentColor={accentColor} />
        </Field>
      </Section>

      <Section title="Staging & External" icon={Cloud} accentColor={accentColor}>
        <Field label="Namespace" description="K8s namespace or prefix for staging environments." isOverride={isOverride('staging.namespace')}>
          <Input value={getVal('staging.namespace')} onChange={(v) => handleChange('staging.namespace', v)} />
        </Field>
        <Field label="Environment" description="Target environment name (e.g. 'local', 'dev')." isOverride={isOverride('staging.environment')}>
          <Input value={getVal('staging.environment')} onChange={(v) => handleChange('staging.environment', v)} />
        </Field>
        <Field label="Use Google Sheets" description="Sync project status to a Google Sheet." isOverride={isOverride('use_google_sheets')}>
          <Switch checked={getVal('use_google_sheets')} onChange={(v) => handleChange('use_google_sheets', v)} accentColor={accentColor} />
        </Field>
        <Field label="Sheet ID" isOverride={isOverride('google_sheet_id')}>
          <Input value={getVal('google_sheet_id')} onChange={(v) => handleChange('google_sheet_id', v)} />
        </Field>
      </Section>

      <Section title="Coverage Targets (%)" icon={Activity} accentColor={accentColor}>
        <Field label="Backend" isOverride={isOverride('coverage_targets.backend')}>
          <Input type="number" value={getVal('coverage_targets.backend')} onChange={(v) => handleChange('coverage_targets.backend', v)} />
        </Field>
        <Field label="Frontend" isOverride={isOverride('coverage_targets.frontend')}>
          <Input type="number" value={getVal('coverage_targets.frontend')} onChange={(v) => handleChange('coverage_targets.frontend', v)} />
        </Field>
        <Field label="Tauri" isOverride={isOverride('coverage_targets.tauri')}>
          <Input type="number" value={getVal('coverage_targets.tauri')} onChange={(v) => handleChange('coverage_targets.tauri', v)} />
        </Field>
        <Field label="Infrastructure" isOverride={isOverride('coverage_targets.infra')}>
          <Input type="number" value={getVal('coverage_targets.infra')} onChange={(v) => handleChange('coverage_targets.infra', v)} />
        </Field>
      </Section>

      <Section title="Task Iterations" icon={Repeat} accentColor={accentColor}>
        <Field label="Implementation" isOverride={isOverride('iterations.implementation')}>
          <Input type="number" value={getVal('iterations.implementation')} onChange={(v) => handleChange('iterations.implementation', v)} />
        </Field>
        <Field label="Debug" isOverride={isOverride('iterations.debug')}>
          <Input type="number" value={getVal('iterations.debug')} onChange={(v) => handleChange('iterations.debug', v)} />
        </Field>
        <Field label="Testing" isOverride={isOverride('iterations.test_fix')}>
          <Input type="number" value={getVal('iterations.test_fix')} onChange={(v) => handleChange('iterations.test_fix', v)} />
        </Field>
        <Field label="PRD Interview" isOverride={isOverride('iterations.prd_interview')}>
          <Input type="number" value={getVal('iterations.prd_interview')} onChange={(v) => handleChange('iterations.prd_interview', v)} />
        </Field>
      </Section>

      <Section title="Infrastructure & Services" icon={Database} accentColor={accentColor}>
        <Field label="Use Google Sheets" description="Sync project status to a Google Sheet." isOverride={isOverride('use_google_sheets')}>
          <Switch checked={getVal('use_google_sheets')} onChange={(v) => handleChange('use_google_sheets', v)} accentColor={accentColor} />
        </Field>
        <Field label="Sheet ID" isOverride={isOverride('google_sheet_id')}>
          <Input value={getVal('google_sheet_id')} onChange={(v) => handleChange('google_sheet_id', v)} />
        </Field>
      </Section>

      <Section title="Common Services" icon={Database} accentColor={accentColor}>
        <div className="col-span-full space-y-6">
          {servers.map((server) => {
            const isConfigured = !!config.services?.[server.name];
            return (
              <div key={server.name} className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 transition-all hover:border-zinc-700/50 group">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-8 h-8 rounded-lg flex items-center justify-center border transition-colors",
                      server.status === 'running' ? "bg-green-500/10 border-green-500/20 text-green-400" : 
                      server.status === 'not_created' ? "bg-zinc-800 border-zinc-700 text-zinc-500" :
                      "bg-red-500/10 border-red-500/20 text-red-400"
                    )}>
                      {server.name === 'postgres' ? <Database size={16} /> : 
                       server.name === 'redis' ? <Zap size={16} /> : 
                       server.name === 'rabbitmq' ? <Network size={16} /> : 
                       <Layers size={16} />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold text-zinc-200 uppercase tracking-widest">{server.name}</h4>
                        <span className={cn(
                          "text-[8px] px-1 py-0 rounded uppercase tracking-tighter border",
                          server.status === 'running' ? "bg-green-500/10 text-green-500 border-green-500/20" : 
                          server.status === 'not_created' ? "bg-zinc-800 text-zinc-500 border-zinc-700" :
                          "bg-red-500/10 text-red-500 border-red-500/20"
                        )}>
                          {server.status.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-[10px] text-zinc-500 mt-0.5">{server.description}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button 
                      onClick={() => handleServerAction(server.name, 'start')}
                      className="p-1.5 rounded-md hover:bg-green-500/10 hover:text-green-400 text-zinc-500 transition-colors"
                      title="Start"
                    >
                      <Play size={14} />
                    </button>
                    <button 
                      onClick={() => handleServerAction(server.name, 'stop')}
                      className="p-1.5 rounded-md hover:bg-red-500/10 hover:text-red-400 text-zinc-500 transition-colors"
                      title="Stop"
                    >
                      <Square size={14} />
                    </button>
                    <button 
                      onClick={() => handleServerAction(server.name, 'restart')}
                      className="p-1.5 rounded-md hover:bg-blue-500/10 hover:text-blue-400 text-zinc-500 transition-colors"
                      title="Restart"
                    >
                      <RefreshCw size={14} />
                    </button>
                    <button 
                      onClick={() => setActiveLogOverlay(server)}
                      className="p-1.5 rounded-md hover:bg-zinc-800 hover:text-zinc-200 text-zinc-500 transition-colors"
                      title="Logs"
                    >
                      <Terminal size={14} />
                    </button>
                    <div className="w-px h-4 bg-zinc-800 mx-1" />
                    <button 
                      onClick={() => handleAutoFill(server.name)}
                      className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-white transition-all text-[10px] font-bold uppercase tracking-wider"
                      title="Get config from running container"
                    >
                      <Search size={10} />
                      Sync
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 pt-4 border-t border-zinc-800/50">
                  <Field label="Host" isOverride={isOverride(`services.${server.name}.host`)}>
                    <Input value={getVal(`services.${server.name}.host`)} onChange={(v) => handleChange(`services.${server.name}.host`, v)} />
                  </Field>
                  <Field label="Port" isOverride={isOverride(`services.${server.name}.port`)}>
                    <Input type="number" value={getVal(`services.${server.name}.port`)} onChange={(v) => handleChange(`services.${server.name}.port`, v)} />
                  </Field>
                  {server.name === 'postgres' && (
                    <>
                      <Field label="User" isOverride={isOverride(`services.${server.name}.user`)}>
                        <Input value={getVal(`services.${server.name}.user`)} onChange={(v) => handleChange(`services.${server.name}.user`, v)} />
                      </Field>
                      <Field label="Password" isOverride={isOverride(`services.${server.name}.password`)}>
                        <Input value={getVal(`services.${server.name}.password`)} onChange={(v) => handleChange(`services.${server.name}.password`, v)} />
                      </Field>
                      <Field label="Database" isOverride={isOverride(`services.${server.name}.database`)}>
                        <Input value={getVal(`services.${server.name}.database`)} onChange={(v) => handleChange(`services.${server.name}.database`, v)} />
                      </Field>
                    </>
                  )}
                  {(server.name === 'minio-linode' || server.name === 'minio-aws') && (
                    <>
                      <Field label="Access Key" isOverride={isOverride(`services.${server.name}.access_key`)}>
                        <Input value={getVal(`services.${server.name}.access_key`)} onChange={(v) => handleChange(`services.${server.name}.access_key`, v)} />
                      </Field>
                      <Field label="Secret Key" isOverride={isOverride(`services.${server.name}.secret_key`)}>
                        <Input value={getVal(`services.${server.name}.secret_key`)} onChange={(v) => handleChange(`services.${server.name}.secret_key`, v)} />
                      </Field>
                    </>
                  )}
                </div>
              </div>
            );
          })}
          
          {servers.length === 0 && !loadingServers && (
            <div className="text-center py-10 border-2 border-dashed border-zinc-800 rounded-2xl">
              <p className="text-zinc-500 text-sm">No server definitions found. Make sure vibe-tools is installed correctly.</p>
              <button 
                onClick={fetchServers}
                className="mt-4 px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors text-xs font-bold uppercase tracking-widest"
              >
                Retry Scan
              </button>
            </div>
          )}
        </div>
      </Section>

      {activeLogService && (
        <ServiceLogOverlay 
          service={activeLogService} 
          onClose={() => setActiveLogOverlay(null)} 
          accentColor={accentColor}
          onAction={(action) => handleServerAction(activeLogService.name, action)}
        />
      )}
    </div>
  );
};

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import Ansi from 'ansi-to-react';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle, useDefaultLayout } from 'react-resizable-panels';
import {
  MessageSquare,
  Files,
  Activity,
  PlayCircle,
  TestTube,
  LayoutDashboard,
  Layout,
  ChevronLeft,
  ChevronRight,
  Terminal,
  Wrench,
  Database,
  Folder,
  FileText,
  Send,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  AlertCircle,
  Link as LinkIcon,
  User as UserIcon,
  Tag,
  ArrowRight,
  Split,
  History,
  Trash2,
  RefreshCw,
  Eye,
  Settings,
  PencilLine,
  Kanban,
  Bug,
  Shield,
  Coins,
  ChevronDown,
  Network,
  Sun,
  Moon,
  Sunrise,
  Sunset,
  BarChart3,
  PanelLeft,
  PanelRight,
  Columns,
  X
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import yaml from 'js-yaml';
import appIcon from './app-icon.png';
// import mermaid from 'mermaid';
import { PlannerSidebar } from './layout/PlannerSidebar';
import { IssuesSidebar } from './layout/IssuesSidebar';
import { StatsSidebar } from './layout/StatsSidebar';
import { ProjectsSidebar } from './layout/ProjectsSidebar';
import { Accordion } from './components/Accordion';
import { VibeSidebar, Artifact } from './components/VibeSidebar';
import { AgentInteraction, Message, AgentProcess } from './components/AgentInteraction';
import { PlannerBoard } from './components/PlannerBoard';
import { PlannerGraph } from './components/PlannerGraph';
import { UnifiedLogMonitor } from './components/UnifiedLogMonitor';
import { ConfigForm } from './components/ConfigForm';
import { EnvEditor } from './components/EnvEditor';
import { StatsView } from './components/StatsView';
import { InterfaceDesigner } from './components/InterfaceDesigner';
import { DatabaseDesigner } from './components/DatabaseDesigner';
import { PRDEditor } from './components/PRDEditor';

import { chatStore } from './ChatStore';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type Tab = 'setup' | 'planner' | 'issues' | 'projects' | 'settings' | 'env' | 'stats' | 'interface-designer' | 'database-designer';

type ThemeMode = 'night' | 'day' | 'morning' | 'sunset';

type ThemeColors = {
  bg: string,
  text: string,
  panel: string,
  border: string,
  muted: string,
  input: string,
  isDark: boolean
};

const DEFAULT_THEMES: Record<ThemeMode, ThemeColors> = {
  night: {
    bg: '#09090b',
    text: '#f4f4f5',
    panel: 'rgba(24, 24, 27, 0.5)',
    border: '#27272a',
    muted: '#71717a',
    input: '#18181b',
    isDark: true
  },
  day: {
    bg: '#fafafa',
    text: '#09090b',
    panel: '#ffffff',
    border: '#d4d4d8',
    muted: '#52525b',
    input: '#ffffff',
    isDark: false
  },
  morning: {
    bg: '#f0f9ff',
    text: '#082f49',
    panel: 'rgba(236, 253, 245, 0.8)',
    border: '#a7f3d0',
    muted: '#047857',
    input: '#ffffff',
    isDark: false
  },
  sunset: {
    bg: '#fff7ed',
    text: '#431407',
    panel: 'rgba(254, 252, 232, 0.8)',
    border: '#fef08a',
    muted: '#9a3412',
    input: '#ffffff',
    isDark: false
  }
};

interface Project {
  id: string;
  name: string;
  path: string;
  description?: string;
  last_active?: string;
  metadata?: Record<string, any>;
  secrets?: Record<string, string>;
  theme?: ThemeMode;
  color?: string;
}

interface ProjectRegistry {
  projects: Project[];
  last_active_project_id: string | null;
}

const ColorPicker = ({ label, value, onChange }: { label: string, value: string, onChange: (v: string) => void }) => (
  <div className="flex items-center gap-3">
    <div className="flex-1">
      <div className="text-[9px] text-muted font-bold uppercase mb-1">{label}</div>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-input border border-border rounded px-2 py-1 text-[10px] font-mono text-muted focus:outline-none"
      />
    </div>
    <div className="relative group">
      <div
        className="w-8 h-8 rounded border border-border cursor-pointer"
        style={{ backgroundColor: value }}
      />
      <input
        type="color"
        value={value.startsWith('#') ? value.slice(0, 7) : '#000000'}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 opacity-0 cursor-pointer"
      />
    </div>
  </div>
);

const ProjectSettingsEditor = ({
  project,
  workspaceRoot,
  onSave,
  onThemeChange,
  onColorChange
}: {
  project: Project,
  workspaceRoot: string,
  onSave: () => void,
  onThemeChange: (theme: ThemeMode) => void,
  onColorChange: (color: string) => void
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'colors' | 'config' | 'envs'>('config');
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [name] = useState(project.name);
  const [path] = useState(project.path);
  const [githubUrl] = useState(project.metadata?.github_url || '');
  const [theme, setTheme] = useState<ThemeMode>((project.metadata?.theme as ThemeMode) || 'night');
  const [color, setColor] = useState((project.metadata?.color as string) || '#3b82f6');
  const [themeColors, setThemeColors] = useState<Record<ThemeMode, ThemeColors>>({
    ...DEFAULT_THEMES,
    ...(project.metadata?.theme_colors || {})
  });

  const handleThemeColorChange = (mode: ThemeMode, key: keyof ThemeColors, value: any) => {
    setThemeColors(prev => ({
      ...prev,
      [mode]: {
        ...prev[mode],
        [key]: value
      }
    }));
  };

  const handleThemeChange = (newTheme: ThemeMode) => {
    setTheme(newTheme);
    onThemeChange(newTheme);
  };

  const handleColorChange = (newColor: string) => {
    setColor(newColor);
    onColorChange(newColor);
  };

  useEffect(() => {
    const configPath = `${workspaceRoot}/implementation/config.json`;
    invoke<string>('read_file_content', { path: configPath })
      .then(content => {
        try {
          const parsed = JSON.parse(content);
          setConfig(parsed);
        } catch (e) {
          console.error("Error parsing config.json, using empty object", e);
          setConfig({});
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Error reading config.json:", err);
        setConfig({});
        setLoading(false);
      });
  }, [workspaceRoot]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const configPath = `${workspaceRoot}/implementation/config.json`;
      const finalConfig = JSON.stringify(config, null, 2);
      await invoke('write_file_content', { path: configPath, content: finalConfig });

      await invoke('update_project_registry', {
        id: project.id,
        name: name,
        path: path,
        description: project.description,
        metadata: {
          ...project.metadata,
          theme,
          color,
          github_url: githubUrl,
          theme_colors: themeColors
        },
        secrets: project.secrets || {}
      });

      onSave();
    } catch (err) {
      alert(`Error saving settings: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-muted">
      <RefreshCw size={32} className="animate-spin opacity-20" />
      <span className="text-sm font-medium">Loading project configuration...</span>
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6 p-10">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-8">
        <div>
          <h2 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <Settings size={28} style={{ color: color }} />
            Project Settings
          </h2>
          <p className="text-muted mt-2">Manage project-specific rules, appearance, and environment</p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => onSave()}
            className="px-4 py-2 text-muted hover:text-foreground transition-colors text-sm font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-8 py-2.5 disabled:opacity-50 text-white rounded-lg text-sm font-bold transition-all flex items-center gap-2 shadow-lg shadow-accent/10"
            style={{ backgroundColor: color }}
          >
            {saving ? <RefreshCw size={18} className="animate-spin" /> : <CheckCircle2 size={18} />}
            {saving ? "Saving..." : "Save All Changes"}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-zinc-800 pb-px">
        {[
          { id: 'config', label: 'Configuration', icon: Settings },
          { id: 'colors', label: 'Theme & Style', icon: Eye },
          { id: 'envs', label: 'Environment', icon: Shield },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id as any)}
            className={cn(
              "flex items-center gap-2 px-6 py-3 text-xs font-bold uppercase tracking-widest transition-all border-b-2",
              activeSubTab === tab.id
                ? "text-foreground border-foreground"
                : "text-muted hover:text-foreground border-transparent"
            )}
            style={activeSubTab === tab.id ? { borderBottomColor: color, color: color } : {}}
          >
            <tab.icon size={14} />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="pt-6">
        {activeSubTab === 'colors' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
            <section className="bg-panel border border-border rounded-2xl p-6 space-y-6">
              <h3 className="text-xs font-bold text-muted flex items-center gap-2 uppercase tracking-widest">
                <Eye size={16} />
                Theme Mode
              </h3>
              <div className="grid grid-cols-2 gap-2">
                {(['night', 'day', 'morning', 'sunset'] as ThemeMode[]).map(m => (
                  <button
                    key={m}
                    onClick={() => handleThemeChange(m)}
                    className={cn(
                      "px-3 py-2.5 rounded-xl border text-xs font-bold transition-all capitalize flex items-center justify-center gap-2",
                      theme === m
                        ? (themeColors[m].isDark ? "bg-zinc-800 border-zinc-600 text-foreground" : "bg-zinc-200 border-zinc-300 text-foreground")
                        : (themeColors[m].isDark ? "bg-zinc-950/50 border-zinc-800/50 text-muted hover:text-foreground hover:bg-zinc-900" : "bg-zinc-50 border-zinc-200 text-muted hover:text-foreground hover:bg-zinc-100")
                    )}
                    style={theme === m ? { borderColor: color, color: color } : {}}
                  >
                    <div className={cn("w-2 h-2 rounded-full")} style={{ backgroundColor: themeColors[m].bg === '#09090b' ? '#3b82f6' : themeColors[m].bg }} />
                    {m}
                  </button>
                ))}
              </div>

              <div>
                <label className="text-[10px] font-bold text-muted uppercase tracking-widest mb-3 block">Accent Color</label>
                <div className="flex items-center gap-4">
                  <div
                    className="w-12 h-12 rounded-xl border border-zinc-800 shadow-inner flex-shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <div className="flex-1 space-y-2">
                    <input
                      type="color"
                      value={color}
                      onChange={(e) => handleColorChange(e.target.value)}
                      className="w-full h-8 bg-transparent border-0 cursor-pointer rounded-lg"
                    />
                    <input
                      type="text"
                      value={color}
                      onChange={(e) => handleColorChange(e.target.value)}
                      className="w-full bg-input border border-border rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-accent text-muted"
                    />
                  </div>
                </div>
              </div>
            </section>

            <section className="bg-panel border border-border rounded-2xl p-6 space-y-6">
              <h3 className="text-xs font-bold text-muted flex items-center gap-2 uppercase tracking-widest">
                <PencilLine size={16} />
                Custom Mode Colors ({theme})
              </h3>
              <div className="space-y-4">
                <ColorPicker
                  label="Background"
                  value={themeColors[theme].bg}
                  onChange={(v) => handleThemeColorChange(theme, 'bg', v)}
                />
                <ColorPicker
                  label="Text"
                  value={themeColors[theme].text}
                  onChange={(v) => handleThemeColorChange(theme, 'text', v)}
                />
                <ColorPicker
                  label="Panel"
                  value={themeColors[theme].panel}
                  onChange={(v) => handleThemeColorChange(theme, 'panel', v)}
                />
                <ColorPicker
                  label="Border"
                  value={themeColors[theme].border}
                  onChange={(v) => handleThemeColorChange(theme, 'border', v)}
                />
                <ColorPicker
                  label="Muted"
                  value={themeColors[theme].muted}
                  onChange={(v) => handleThemeColorChange(theme, 'muted', v)}
                />
                <div className="flex items-center justify-between pt-2">
                  <span className="text-[10px] text-muted font-bold uppercase">Dark Mode</span>
                  <input
                    type="checkbox"
                    checked={themeColors[theme].isDark}
                    onChange={(e) => handleThemeColorChange(theme, 'isDark', e.target.checked)}
                    className="rounded border-zinc-800 bg-zinc-950 text-accent focus:ring-accent/50"
                  />
                </div>
              </div>
            </section>
          </div>
        )}

        {activeSubTab === 'config' && config && (
          <div className="lg:col-span-2">
            <div className="bg-panel border border-border rounded-2xl overflow-hidden flex flex-col min-h-[600px]">
              <div className="px-6 py-4 bg-panel border-b border-border flex items-center justify-between shrink-0">
                <h3 className="text-xs font-bold text-muted flex items-center gap-2 uppercase tracking-widest">
                  <Settings size={16} />
                  Project Rules & Agent Configuration
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
                <ConfigForm config={config} onChange={setConfig} accentColor={color} />
              </div>
            </div>
            <p className="mt-3 text-[10px] text-muted flex items-center gap-1.5 px-2">
              <AlertCircle size={10} />
              These settings are stored in `implementation/config.json` and affect how AI agents interact with your codebase.
            </p>
          </div>
        )}

        {activeSubTab === 'envs' && (
          <div className="bg-panel border border-border rounded-2xl overflow-hidden">
            <EnvEditor
              workspaceRoot={workspaceRoot}
              accentColor={color}
            />
          </div>
        )}
      </div>
    </div>
  );
};

const TerminalOutputView = ({ accentColor }: { accentColor: string }) => {
  const [terminalOutput, setTerminalOutput] = useState<string[]>([]);
  const [isLive, setIsLive] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const logQueue = useRef<string[]>([]);
  const flushTimer = useRef<any>(null);

  useEffect(() => {
    invoke<string[]>('get_terminal_buffer', { session: 'main' })
      .then(setTerminalOutput);

    const flushLogs = () => {
      if (logQueue.current.length > 0) {
        const toAdd = [...logQueue.current];
        logQueue.current = [];
        setTerminalOutput(prev => [...prev, ...toAdd].slice(-1000));
      }
      flushTimer.current = null;
    };

    const unlisten = listen('log-line', (event: any) => {
      if (!isLive) return;
      logQueue.current.push(event.payload as string);
      if (!flushTimer.current) {
        flushTimer.current = setTimeout(flushLogs, 200);
      }
    });

    return () => { 
      unlisten.then(f => f()); 
      if (flushTimer.current) clearTimeout(flushTimer.current);
    };
  }, [isLive]);

  useEffect(() => {
    if (scrollRef.current && isLive) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [terminalOutput, isLive]);

  return (
    <div className="flex flex-col h-full bg-black/20 rounded-lg overflow-hidden border border-border/50">
      <div className="flex items-center justify-between px-3 py-1.5 bg-panel border-b border-border/50 shrink-0">
        <div className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-widest text-muted">
          <Terminal size={12} />
          Terminal Output
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setIsLive(!isLive)}
            className={cn(
              "px-2 py-0.5 rounded text-[9px] font-bold uppercase transition-all",
              isLive ? "bg-green-500/10 text-green-500 border border-green-500/20" : "bg-zinc-800 text-muted border border-border"
            )}
          >
            {isLive ? 'Live' : 'Paused'}
          </button>
          <button 
            onClick={() => setTerminalOutput([])}
            className="px-2 py-0.5 rounded text-[9px] font-bold uppercase text-muted hover:text-foreground transition-colors"
          >
            Clear
          </button>
        </div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 font-mono text-[10px] space-y-0.5 scrollbar-thin">
        {terminalOutput.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap break-all leading-relaxed text-muted/80">
            <Ansi>{line}</Ansi>
          </div>
        ))}
        {isLive && <div className="inline-block w-1.5 h-3 bg-accent/30 ml-1 animate-pulse" style={{ backgroundColor: accentColor + '33' }} />}
      </div>
    </div>
  );
};

const ProjectManagerView = ({
  registry,
  onSwitch,
  onRefresh
}: {
  registry: ProjectRegistry,
  onSwitch: (p: Project) => void,
  onRefresh: () => void
}) => {
  const [importPath, setImportPath] = useState('');
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [editName, setEditName] = useState('');
  const [editPath, setEditPath] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editGithub, setEditGithub] = useState('');
  const [editSecrets, setEditSecrets] = useState('');

  const handleImport = async () => {
    if (!importPath) return;
    try {
      await invoke('run_vibe_command', { command: 'project', args: ['add', importPath] });
      setImportPath('');
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRemove = async (id: string) => {
    if (!confirm('Are you sure you want to remove this project from the registry?')) return;
    try {
      await invoke('run_vibe_command', { command: 'project', args: ['remove', id] });
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  const startEditing = (p: Project) => {
    setEditingProject(p);
    setEditName(p.name);
    setEditPath(p.path);
    setEditDesc(p.description || '');
    setEditGithub(p.metadata?.github_url || '');
    setEditSecrets(JSON.stringify(p.secrets || {}, null, 2));
  };

  const saveEdit = async () => {
    if (!editingProject) return;
    try {
      let secretsObj = {};
      try {
        secretsObj = JSON.parse(editSecrets);
      } catch (e) {
        alert('Invalid JSON for secrets');
        return;
      }

      await invoke('update_project_registry', {
        id: editingProject.id,
        name: editName,
        path: editPath,
        description: editDesc,
        metadata: {
          ...editingProject.metadata,
          github_url: editGithub
        },
        secrets: secretsObj
      });

      setEditingProject(null);
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Project Manager</h2>
          <p className="text-sm text-muted mt-1">Manage and switch between your vibe projects</p>
        </div>
        {!editingProject && (
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Path to project..."
              value={importPath}
              onChange={(e) => setImportPath(e.target.value)}
              className="bg-input border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-accent w-64 text-foreground"
            />
            <button
              onClick={handleImport}
              className="flex items-center gap-2 px-4 py-1.5 bg-accent hover:bg-accent/80 text-white rounded-md text-sm font-bold transition-colors"
            >
              Import Project
            </button>
          </div>
        )}
      </div>

      {editingProject ? (
        <div className="bg-panel border border-border rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-bold text-foreground">Edit Project: {editingProject.name}</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-widest">Name</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full bg-input border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent text-foreground"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-widest">Path</label>
              <input
                type="text"
                value={editPath}
                onChange={(e) => setEditPath(e.target.value)}
                className="w-full bg-input border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent text-foreground"
              />
            </div>
            <div className="col-span-2 space-y-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-widest">GitHub URL</label>
              <input
                type="text"
                value={editGithub}
                onChange={(e) => setEditGithub(e.target.value)}
                className="w-full bg-input border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent text-foreground"
              />
            </div>
            <div className="col-span-2 space-y-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-widest">Description</label>
              <input
                type="text"
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                className="w-full bg-input border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent text-foreground"
              />
            </div>
            <div className="col-span-2 space-y-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-widest">Secrets (JSON)</label>
              <textarea
                value={editSecrets}
                onChange={(e) => setEditSecrets(e.target.value)}
                rows={5}
                className="w-full bg-input border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent text-foreground"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button
              onClick={() => setEditingProject(null)}
              className="px-4 py-2 text-sm font-medium text-muted hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={saveEdit}
              className="px-6 py-2 bg-accent hover:bg-accent/80 text-white rounded-md text-sm font-bold transition-colors"
            >
              Save Changes
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {registry.projects.map((project) => (
            <div
              key={project.id}
              className={cn(
                "p-5 rounded-xl border transition-all flex items-center justify-between group",
                registry.last_active_project_id === project.id
                  ? "bg-accent/5 border-accent/30"
                  : "bg-panel border-border hover:border-zinc-700"
              )}
            >
              <div className="flex-1 min-w-0 pr-8">
                <div className="flex items-center gap-3 mb-1">
                  <h3 className="text-lg font-bold text-foreground truncate">{project.name}</h3>
                  {registry.last_active_project_id === project.id && (
                    <span className="px-2 py-0.5 rounded-full bg-accent/10 text-accent text-[10px] font-bold uppercase tracking-wider">Active</span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-muted text-sm font-mono truncate mb-2">
                  <Folder size={14} />
                  <span>{project.path}</span>
                </div>
                {project.description && (
                  <p className="text-sm text-muted line-clamp-1 opacity-80">{project.description}</p>
                )}
                <div className="flex items-center gap-4 mt-3">
                  <div className="text-[10px] text-muted font-medium uppercase tracking-widest opacity-70">
                    Last active: {project.last_active ? new Date(project.last_active).toLocaleString() : 'Never'}
                  </div>
                  {project.metadata?.github_url && (
                    <div className="flex items-center gap-1 text-[10px] text-accent/70 font-medium uppercase tracking-widest">
                      <LinkIcon size={10} />
                      GitHub Linked
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => startEditing(project)}
                  className="p-2 text-muted hover:text-foreground transition-colors"
                  title="Edit Project"
                >
                  <History size={18} />
                </button>
                <button
                  onClick={() => onSwitch(project)}
                  disabled={registry.last_active_project_id === project.id}
                  className={cn(
                    "px-4 py-2 rounded-lg text-sm font-bold transition-all",
                    registry.last_active_project_id === project.id
                      ? "bg-zinc-800 text-muted cursor-default"
                      : "bg-zinc-100 text-zinc-950 hover:bg-white"
                  )}
                >
                  {registry.last_active_project_id === project.id ? "Current" : "Switch to Project"}
                </button>
                <button
                  onClick={() => handleRemove(project.id)}
                  className="p-2 text-muted hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                  title="Remove from registry"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}

          {registry.projects.length === 0 && (
            <div className="h-64 flex flex-col items-center justify-center text-muted bg-panel/30 border border-dashed border-border rounded-xl">
              <LayoutDashboard size={48} className="mb-4 opacity-10" />
              <p className="text-lg font-medium text-muted">No projects registered yet</p>
              <p className="text-sm mt-1">Import an existing project or use 'vibe init' in the CLI</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};


const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    return (localStorage.getItem('vibe-active-tab') as Tab) || 'planner';
  });
  const [vibeExplorerRefreshKey, setVibeExplorerRefreshKey] = useState(0);
  const [workspaceRoot, setWorkspaceRoot] = useState<string>('');
  const [activeAgents] = useState<AgentProcess[]>([]);
  const [totalCost, setTotalCost] = useState<number>(0);
  const [projectRegistry, setProjectRegistry] = useState<ProjectRegistry>({ projects: [], last_active_project_id: null });
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(() => {
    const saved = localStorage.getItem('vibe-selected-artifact');
    if (!saved) return null;
    try {
      return JSON.parse(saved);
    } catch (e) {
      return null;
    }
  });

  const [openArtifacts, setOpenArtifacts] = useState<Artifact[]>(() => {
    const saved = localStorage.getItem('vibe-open-artifacts');
    if (!saved) return [];
    try {
      return JSON.parse(saved);
    } catch (e) {
      return [];
    }
  });

  const [showGlobalLeft, setShowGlobalLeft] = useState(() => {
    return localStorage.getItem('vibe-show-global-left') !== 'false';
  });
  const [showLeft, setShowLeft] = useState(() => {
    return localStorage.getItem('vibe-show-left') !== 'false';
  });
  const [showRight, setShowRight] = useState(() => {
    return localStorage.getItem('vibe-show-right') !== 'false';
  });
  const [showTerminal, setShowTerminal] = useState(() => {
    return localStorage.getItem('vibe-show-terminal') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('vibe-open-artifacts', JSON.stringify(openArtifacts));
  }, [openArtifacts]);

  useEffect(() => {
    localStorage.setItem('vibe-show-terminal', String(showTerminal));
  }, [showTerminal]);

  useEffect(() => {
    localStorage.setItem('vibe-show-global-left', String(showGlobalLeft));
  }, [showGlobalLeft]);

  useEffect(() => {
    localStorage.setItem('vibe-show-left', String(showLeft));
  }, [showLeft]);

  useEffect(() => {
    localStorage.setItem('vibe-show-right', String(showRight));
  }, [showRight]);

  const addToOpenArtifacts = useCallback((artifact: Artifact) => {
    setOpenArtifacts(prev => {
      if (prev.find(a => a.path === artifact.path)) return prev;
      return [...prev, artifact];
    });
  }, []);

  const closeArtifact = useCallback((path: string) => {
    setOpenArtifacts(prev => {
      const filtered = prev.filter(a => a.path !== path);
      if (selectedArtifact?.path === path) {
        setSelectedArtifact(filtered.length > 0 ? filtered[filtered.length - 1] : null);
      }
      return filtered;
    });
  }, [selectedArtifact]);

  const handleArtifactsLoaded = useCallback((freshArtifacts: Artifact[]) => {
    setOpenArtifacts(prev => {
      let changed = false;
      const next = prev.map(art => {
        // 1. Try to find by exact path
        const fresh = freshArtifacts.find(f => f.path === art.path);
        if (fresh) {
          if (art.deleted) {
            changed = true;
            return { ...fresh, deleted: false };
          }
          // Check if name or status changed
          if (fresh.name !== art.name || fresh.status !== art.status) {
            changed = true;
            return { ...art, ...fresh, deleted: false };
          }
          return art;
        }

        // 2. Not found by path, try to find by ID
        if (art.id) {
          const byId = freshArtifacts.find(f => f.id === art.id);
          if (byId) {
            changed = true;
            // Update path and name (rename/move)
            return { ...art, ...byId, deleted: false };
          }
        }

        // 3. Truly not found
        if (!art.deleted) {
          changed = true;
          return { ...art, deleted: true };
        }
        return art;
      });

      if (changed) {
        // Also update selected artifact if it was updated
        if (selectedArtifact) {
          const updatedSelected = next.find(a => 
            (selectedArtifact.id && a.id === selectedArtifact.id) || 
            a.path === selectedArtifact.path
          );
          if (updatedSelected && (updatedSelected.path !== selectedArtifact.path || updatedSelected.name !== selectedArtifact.name || updatedSelected.deleted !== selectedArtifact.deleted)) {
            setSelectedArtifact(updatedSelected);
          }
        }

        // Also update editing PRD if it was updated
        if (editingPRD) {
          const updatedEditing = next.find(a => 
            (editingPRD.id && a.id === editingPRD.id) || 
            a.path === editingPRD.path
          );
          if (updatedEditing && (updatedEditing.path !== editingPRD.path || updatedEditing.name !== editingPRD.name || updatedEditing.deleted !== editingPRD.deleted)) {
            setEditingPRD((prev: any) => ({ 
              ...prev, 
              ...updatedEditing,
              filename: updatedEditing.name,
              title: updatedEditing.name
            }));
          }
        }
      }

      return changed ? next : prev;
    });
  }, [selectedArtifact]);

  const toggleGlobalLeft = useCallback(() => {
    setShowGlobalLeft(prev => !prev);
  }, []);

  const toggleLeft = useCallback(() => {
    setShowLeft(prev => !prev);
  }, []);

  const toggleRight = useCallback(() => {
    setShowRight(prev => !prev);
  }, []);

  const activeTabRef = useRef<Tab>(activeTab);
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);

  useEffect(() => {
    if (selectedArtifact) {
      localStorage.setItem('vibe-selected-artifact', JSON.stringify(selectedArtifact));
    } else {
      localStorage.removeItem('vibe-selected-artifact');
    }
  }, [selectedArtifact]);

  const [currentTheme, setCurrentTheme] = useState<ThemeMode>(() => {
    return (localStorage.getItem('vibe-theme') as ThemeMode) || 'night';
  });
  const [accentColor, setAccentColor] = useState<string>(() => {
    return localStorage.getItem('vibe-accent-color') || '#3b82f6';
  });
  const [customThemeColors, setCustomThemeColors] = useState<Record<ThemeMode, ThemeColors>>(() => {
    const saved = localStorage.getItem('vibe-custom-theme-colors');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return DEFAULT_THEMES;
      }
    }
    return DEFAULT_THEMES;
  });
  const [interactionMode, setInteractionMode] = useState<'ASK' | 'AGENT'>(() => {
    return (localStorage.getItem('vibe-interaction-mode') as 'ASK' | 'AGENT') || 'ASK';
  });
  const [statsPeriod, setStatsPeriod] = useState<string>(() => {
    return localStorage.getItem('vibe-stats-period') || 'month';
  });

  const [editingPRD, setEditingPRD] = useState<any | null>(null);

  const handleEditPRD = useCallback(async (prd: any) => {
    try {
      const content = await invoke<string>('read_file_content', { path: prd.path });
      const prdData = {
        id: prd.id || prd.name.replace('.md', ''),
        title: prd.name,
        path: prd.path,
        filename: prd.name,
        status: prd.status || '',
        columnId: '',
        initialContent: content
      };

      const artifact: Artifact = {
        id: prdData.id,
        name: prdData.filename,
        path: prdData.path,
        type: 'prd' as const,
        status: prdData.status,
        relPath: prdData.path.replace(workspaceRoot, '')
      };

      addToOpenArtifacts(artifact);
      setSelectedArtifact(artifact);
      setEditingPRD(prdData);
    } catch (err) {
      console.error('Failed to load PRD content:', err);
    }
  }, [workspaceRoot, addToOpenArtifacts]);

  const handleSavePRD = useCallback(async (content: string) => {
    if (!editingPRD) return;
    try {
      await invoke('write_file_content', { path: editingPRD.path, content });
      setEditingPRD(null);
    } catch (err) {
      console.error('Failed to save PRD:', err);
      alert('Failed to save PRD.');
    }
  }, [editingPRD]);

  useEffect(() => {
    localStorage.setItem('vibe-stats-period', statsPeriod);
  }, [statsPeriod]);

  useEffect(() => {
    localStorage.setItem('vibe-active-tab', activeTab);
    invoke('emit_log', { level: 'INFO', source: 'UI', message: `Tab changed to: ${activeTab}`, data: null }).catch(() => { });
  }, [activeTab]);

  useEffect(() => {
    localStorage.setItem('vibe-theme', currentTheme);
  }, [currentTheme]);

  useEffect(() => {
    localStorage.setItem('vibe-accent-color', accentColor);
  }, [accentColor]);

  useEffect(() => {
    localStorage.setItem('vibe-custom-theme-colors', JSON.stringify(customThemeColors));
  }, [customThemeColors]);

  useEffect(() => {
    localStorage.setItem('vibe-interaction-mode', interactionMode);
  }, [interactionMode]);

  useEffect(() => {
    const syncMode = async () => {
      try {
        await invoke('run_vibe_command', { command: 'mode', args: [interactionMode.toLowerCase()] });
      } catch (e) {
        // Ignore
      }
    };
    syncMode();
  }, []);

  const themeColors = useMemo(() => {
    return customThemeColors[currentTheme];
  }, [customThemeColors, currentTheme]);

  const loadRegistry = useCallback(async () => {
    try {
      const registry = await invoke<ProjectRegistry>('get_projects');
      setProjectRegistry(registry);

      const active = registry.projects.find(p => p.id === registry.last_active_project_id);
      if (active && active.metadata) {
        if (active.metadata.theme) setCurrentTheme(active.metadata.theme as ThemeMode);
        if (active.metadata.color) setAccentColor(active.metadata.color as string);
        if (active.metadata.theme_colors) {
          setCustomThemeColors({
            ...DEFAULT_THEMES,
            ...active.metadata.theme_colors
          });
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const activeProject = useMemo(() => {
    return projectRegistry.projects.find(p => p.id === projectRegistry.last_active_project_id);
  }, [projectRegistry]);

  const switchProject = useCallback(async (project: Project) => {
    try {
      await invoke('emit_log', { level: 'INFO', source: 'UI', message: `Switching to project: ${project.name}`, data: null });
      await invoke('set_workspace_root', { path: project.path });
      setWorkspaceRoot(project.path);
      await loadRegistry();
    } catch (e) {
      console.error(e);
    }
  }, [loadRegistry]);

  useEffect(() => {
    invoke<string>('get_workspace_root')
      .then(setWorkspaceRoot)
      .catch(console.error);

    loadRegistry();

    const unlistenServer = listen('vibe-server-event', (event: any) => {
      const payload = event.payload;
      if (payload.type === 'prompt') {
        pendingPromptRef.current = payload.message;
      } else if (payload.type === 'result') {
        pendingPromptRef.current = null;
      } else if (payload.type === 'stats_result') {
        if (payload.total_cost !== undefined) {
          setTotalCost(payload.total_cost);
        }
      } else if (payload.type === 'error') {
        const context = activeTabRef.current === 'setup' ? 'setup' : activeTabRef.current === 'issues' ? 'issues' : activeTabRef.current === 'interface-designer' ? 'interface' : activeTabRef.current === 'database-designer' ? 'database' : 'planner';
        chatStore.addMessage(context, {
          role: 'Architect',
          content: `❌ **Error**: ${payload.message}\n\n\`\`\`\n${payload.traceback || ''}\n\`\`\``
        });
      }
    });

    return () => {
      unlistenServer.then(f => f());
    };
  }, [activeTab, loadRegistry]);

  const fetchUsage = useCallback(() => {
    invoke('run_vibe_command', { command: 'usage', args: [] }).catch(() => { });
  }, []);

  useEffect(() => {
    fetchUsage();

    const unlistenFinished = listen('command-finished', (event) => {
      const payload = event.payload as { command: string, status: any };
      if (payload.command === 'update') {
        fetchUsage();
      }
    });

    return () => {
      unlistenFinished.then(f => f());
    };
  }, [fetchUsage]);

  const pendingPromptRef = useRef<string | null>(null);

  const handlePromptSubmit = useCallback(async (val: string, context: 'setup' | 'planner' | 'issues' | 'interface' | 'database') => {
    if (!val.trim()) return;
    const content = val.trim();
    chatStore.addMessage(context, { role: 'User', content: content });
    pendingPromptRef.current = null;
    try {
      await invoke('send_vibe_input', {
        input: content,
        context: context
      });
    } catch (e) {
      console.error('Error sending prompt response:', e);
    }
  }, []);

  const handleCancelCommand = useCallback(async (pid?: number) => {
    try {
      await invoke('send_vibe_input', { input: JSON.stringify({ type: 'cancel' }) });
    } catch (e) {
      if (pid) {
        await invoke('run_vibe_command', { command: 'kill', args: [pid.toString()] });
      }
    }
  }, []);

  const handleSendMessage = useCallback((val: string, context: 'setup' | 'planner' | 'issues' | 'interface' | 'database') => {
    if (pendingPromptRef.current) {
      handlePromptSubmit(val, context);
      return;
    }

    if (!val.trim()) return;

    const content = val.trim();
    chatStore.addMessage(context, { role: 'User', content });

    if (content.startsWith('/')) {
      const cmd = content.slice(1);
      const [base, ...args] = cmd.split(' ');
      invoke('run_vibe_command', {
        command: base,
        args: [...args, `--context=${context}`, `--chat-id=${context}`]
      })
        .catch(err => {
          chatStore.addMessage(context, {
            role: 'Architect',
            content: `Error running command \`${cmd}\`: ${err}`
          });
        });
    } else {
      invoke('send_vibe_input', {
        input: content,
        context: context,
        chat_id: context
      }).catch(err => {
        console.error(`Error sending message to ${context} agent:`, err);
      });
    }
  }, [handlePromptSubmit]);

  const [plannerView, setPlannerView] = useState<'board' | 'graph'>(() => {
    return (localStorage.getItem('vibe-planner-view') as 'board' | 'graph') || 'board';
  });

  useEffect(() => {
    localStorage.setItem('vibe-planner-view', plannerView);
  }, [plannerView]);

  const cycleTheme = () => {
    const modes: ThemeMode[] = ['night', 'day', 'morning', 'sunset'];
    const currentIndex = modes.indexOf(currentTheme);
    const nextIndex = (currentIndex + 1) % modes.length;
    const newTheme = modes[nextIndex];
    setCurrentTheme(newTheme);

    if (activeProject) {
      invoke('update_project_registry', {
        id: activeProject.id,
        name: activeProject.name,
        path: activeProject.path,
        description: activeProject.description,
        metadata: {
          ...activeProject.metadata,
          theme: newTheme
        },
        secrets: activeProject.secrets || {}
      }).then(() => loadRegistry()).catch(console.error);
    }
  };

  const {
    defaultLayout,
    onLayoutChanged,
  } = useDefaultLayout({
    id: "vibe-layout-v2",
    storage: localStorage,
  });

  const handleSelectArtifact = useCallback((artifact: Artifact | null) => {
    setSelectedArtifact(artifact);
    if (artifact) {
      addToOpenArtifacts(artifact);
    }
  }, [addToOpenArtifacts]);

  return (
    <div
      className={cn("flex flex-col h-screen w-full overflow-hidden font-sans transition-colors duration-500")}
      style={{
        '--accent-color': accentColor,
        '--background': themeColors.bg,
        '--foreground': themeColors.text,
        '--panel': themeColors.panel,
        '--border': themeColors.border,
        '--muted': themeColors.muted,
        '--input': themeColors.input,
        backgroundColor: themeColors.bg,
        color: themeColors.text
      } as React.CSSProperties}
    >
      <header className={cn("h-12 border-b flex items-center justify-between px-4 backdrop-blur-sm z-20 bg-panel border-border")}>
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded flex items-center justify-center transition-all shadow-sm overflow-hidden border border-white/10">
            <img src={appIcon} alt="Vibe Logo" className="w-full h-full object-cover" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold leading-none">{activeProject?.name || 'No Project'}</span>
            <span className="text-[10px] font-mono leading-none mt-1 truncate max-w-[200px] text-muted">{workspaceRoot || 'Not connected'}</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1 px-1.5 py-1 rounded-md border bg-panel border-border">
            <button
              onClick={toggleGlobalLeft}
              className={cn("p-1.5 rounded-md transition-colors", showGlobalLeft ? "text-accent bg-accent/5" : "text-muted hover:text-foreground")}
              title="Toggle Global Sidebar"
              style={showGlobalLeft ? { color: accentColor } : {}}
            >
              <Columns size={16} />
            </button>
            <button
              onClick={toggleLeft}
              className={cn("p-1.5 rounded-md transition-colors", showLeft ? "text-accent bg-accent/5" : "text-muted hover:text-foreground")}
              title="Toggle Project Sidebar"
              style={showLeft ? { color: accentColor } : {}}
            >
              <PanelLeft size={16} />
            </button>
            <button
              onClick={toggleRight}
              className={cn("p-1.5 rounded-md transition-colors", showRight ? "text-accent bg-accent/5" : "text-muted hover:text-foreground")}
              title="Toggle AI Sidebar"
              style={showRight ? { color: accentColor } : {}}
            >
              <PanelRight size={16} />
            </button>
            <button
              onClick={() => setShowTerminal(!showTerminal)}
              className={cn("p-1.5 rounded-md transition-colors", showTerminal ? "text-accent bg-accent/5" : "text-muted hover:text-foreground")}
              title="Toggle Terminal Output"
              style={showTerminal ? { color: accentColor } : {}}
            >
              <Terminal size={16} />
            </button>
          </div>

          <div className="flex items-center gap-2 px-1 rounded-md border h-10 bg-panel border-border">
            <TabButton active={activeTab === 'setup'} onClick={() => setActiveTab('setup')} icon={<Wrench size={14} />} label="Setup" accentColor={accentColor} isDark={themeColors.isDark} />
            <TabButton active={activeTab === 'planner'} onClick={() => setActiveTab('planner')} icon={<Kanban size={14} />} label="Planner" accentColor={accentColor} isDark={themeColors.isDark} />
            <TabButton active={activeTab === 'issues'} onClick={() => setActiveTab('issues')} icon={<Bug size={14} />} label="Issues" accentColor={accentColor} isDark={themeColors.isDark} />
            <TabButton active={activeTab === 'interface-designer'} onClick={() => setActiveTab('interface-designer')} icon={<Layout size={14} />} label="Interface" accentColor={accentColor} isDark={themeColors.isDark} />
            <TabButton active={activeTab === 'database-designer'} onClick={() => setActiveTab('database-designer')} icon={<Database size={14} />} label="Database" accentColor={accentColor} isDark={themeColors.isDark} />
            <TabButton active={activeTab === 'stats'} onClick={() => setActiveTab('stats')} icon={<BarChart3 size={14} />} label="Stats" accentColor={accentColor} isDark={themeColors.isDark} />
            <TabButton active={activeTab === 'projects'} onClick={() => setActiveTab('projects')} icon={<LayoutDashboard size={14} />} label="Projects" accentColor={accentColor} isDark={themeColors.isDark} />
          </div>

          <div className="flex items-center gap-2 px-2 py-1 rounded bg-panel border border-border">
            <div className={cn("w-1.5 h-1.5 rounded-full animate-pulse", activeAgents.length > 0 ? "bg-green-500" : "bg-muted")} />
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted">{activeAgents.length > 0 ? 'Working' : 'Idle'}</span>
          </div>

          <button onClick={cycleTheme} className="p-1.5 rounded-md hover:bg-panel text-muted hover:text-foreground transition-colors flex items-center justify-center" title={`Switch Theme (Current: ${currentTheme})`}>
            {currentTheme === 'night' && <Moon size={18} />}
            {currentTheme === 'day' && <Sun size={18} />}
            {currentTheme === 'morning' && <Sunrise size={18} />}
            {currentTheme === 'sunset' && <Sunset size={18} />}
          </button>

          <button onClick={() => setActiveTab('settings')} className={cn("p-1.5 rounded-md transition-colors", activeTab === 'settings' ? "bg-accent text-white" : "hover:bg-panel text-muted hover:text-foreground")} style={activeTab === 'settings' ? { backgroundColor: accentColor } : {}}>
            <Settings size={18} />
          </button>
        </div>
      </header>

      <div className="flex-1 flex flex-col min-h-0">
        <PanelGroup orientation="horizontal" onLayoutChanged={onLayoutChanged} defaultLayout={defaultLayout}>
          {showGlobalLeft && (
            <>
              <Panel
                id="sidebar-global"
                defaultSize={150}
                minSize={150}
                onResize={(size: any) => { if (size < 150) setShowGlobalLeft(false); }}
                className={cn("flex flex-col border-r transition-colors duration-300 bg-background border-border")}
              >
                <div className="flex-1 flex flex-col min-h-0">
                  <div className="p-3 border-b flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-muted">Vibe Explorer</span>
                      <button 
                        onClick={() => setVibeExplorerRefreshKey(prev => prev + 1)}
                        className="p-1 rounded-md hover:bg-panel text-muted hover:text-foreground transition-colors"
                        title="Reload Explorer"
                      >
                        <RefreshCw size={10} />
                      </button>
                    </div>
                    <Files size={12} className="text-muted" />
                  </div>
                  <div className="flex-1 overflow-y-auto p-2 scrollbar-none">
                    <VibeSidebar 
                      root={workspaceRoot} 
                      onSelect={handleSelectArtifact} 
                      onEdit={handleEditPRD} 
                      selectedPath={selectedArtifact?.path} 
                      accentColor={accentColor} 
                      isDark={themeColors.isDark} 
                      refreshKey={vibeExplorerRefreshKey}
                      onArtifactsLoaded={handleArtifactsLoaded}
                    />
                  </div>
                </div>
              </Panel>
              <PanelResizeHandle className="w-1.5 bg-transparent hover:bg-zinc-500/10 active:bg-zinc-500/20 transition-all duration-150" />
            </>
          )}

          {showLeft && (
            <>
              <Panel
                id="sidebar-left"
                defaultSize={200}
                minSize={150}
                onResize={(size: any) => { if (size < 150) setShowLeft(false); }}
                className={cn("flex flex-col border-r shadow-sm transition-colors duration-300 bg-background border-border")}
              >
                {activeTab === 'setup' && (
                  <PlannerSidebar 
                    workspaceRoot={workspaceRoot} 
                    selectedArtifact={selectedArtifact} 
                    onSelectArtifact={handleSelectArtifact} 
                    onEditArtifact={handleEditPRD} 
                    accentColor={accentColor} 
                    isDark={themeColors.isDark} 
                    totalCost={totalCost} 
                    onFetchUsage={fetchUsage} 
                    openArtifacts={openArtifacts}
                    onCloseArtifact={closeArtifact}
                  />
                )}
                {activeTab === 'planner' && (
                  <PlannerSidebar 
                    workspaceRoot={workspaceRoot} 
                    selectedArtifact={selectedArtifact} 
                    onSelectArtifact={handleSelectArtifact} 
                    onEditArtifact={handleEditPRD} 
                    accentColor={accentColor} 
                    isDark={themeColors.isDark} 
                    totalCost={totalCost} 
                    onFetchUsage={fetchUsage} 
                    openArtifacts={openArtifacts}
                    onCloseArtifact={closeArtifact}
                  />
                )}
                {activeTab === 'issues' && <IssuesSidebar isDark={themeColors.isDark} accentColor={accentColor} />}
                {activeTab === 'stats' && <StatsSidebar isDark={themeColors.isDark} accentColor={accentColor} period={statsPeriod} onPeriodChange={setStatsPeriod} loading={false} />}
                {(activeTab === 'projects' || activeTab === 'settings') && <ProjectsSidebar projects={projectRegistry.projects} activeProjectId={projectRegistry.last_active_project_id} onSwitchProject={switchProject} isDark={themeColors.isDark} accentColor={accentColor} />}
              </Panel>
              <PanelResizeHandle className="w-1.5 bg-transparent hover:bg-zinc-500/10 active:bg-zinc-500/20 transition-all duration-150" />
            </>
          )}

          <Panel id="main-content" minSize={30} className="flex flex-col min-w-0">
            <main className="flex-1 overflow-y-auto relative p-6">
              {editingPRD ? <PRDEditor key={editingPRD.id} prd={editingPRD} initialContent={editingPRD.initialContent} onSave={handleSavePRD} onCancel={() => setEditingPRD(null)} accentColor={accentColor} isDark={themeColors.isDark} deleted={editingPRD.deleted} /> :
               activeTab === 'setup' ? <div className="h-full flex flex-col items-center justify-center text-muted"><Wrench size={48} className="mb-4 opacity-10" /><h3 className="text-lg font-medium text-foreground">Initial Setup</h3><p className="text-sm mt-1">Configure your workspace and environment here</p></div> :
               activeTab === 'planner' ? <div className="h-full flex flex-col gap-6 relative">
                 <div className="flex items-center justify-between shrink-0">
                   <div><h2 className="text-2xl font-bold text-foreground">Project Planner</h2><p className="text-sm text-muted mt-1">Manage PRDs and track dependencies</p></div>
                   <div className="flex bg-panel border border-border rounded-lg p-1">
                     <button onClick={() => setPlannerView('board')} className={cn("px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all", plannerView === 'board' ? (themeColors.isDark ? "bg-zinc-800 text-accent shadow-sm" : "bg-zinc-200 text-accent shadow-sm") : "text-muted hover:text-foreground")}><div className="flex items-center gap-2"><Kanban size={12} />Board</div></button>
                     <button onClick={() => setPlannerView('graph')} className={cn("px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all", plannerView === 'graph' ? (themeColors.isDark ? "bg-zinc-800 text-accent shadow-sm" : "bg-zinc-200 text-accent shadow-sm") : "text-muted hover:text-foreground")}><div className="flex items-center gap-2"><Network size={12} />Graph</div></button>
                   </div>
                 </div>
                 <div className="flex-1 min-h-0">
                   {plannerView === 'board' ? <PlannerBoard workspaceRoot={workspaceRoot} onSelectPRD={(prd) => { const artifact = { id: prd.id, name: prd.filename, path: prd.path, type: 'prd' as const, status: prd.status, owner: prd.owner, relPath: prd.path.replace(workspaceRoot, '') }; addToOpenArtifacts(artifact); setSelectedArtifact(artifact); }} onEditPRD={handleEditPRD} onRefresh={loadRegistry} accentColor={accentColor} isDark={themeColors.isDark} /> :
                    <PlannerGraph workspaceRoot={workspaceRoot} onSelectPRD={async (id) => { const entries = await invoke<any[]>('list_directory', { path: `${workspaceRoot}/product/in_progress` }); const entry = entries.find(e => e.name.includes(id)); if (entry) { const artifact = { id: id, name: entry.name, path: entry.path, type: 'prd' as const, relPath: entry.path.replace(workspaceRoot, '') }; addToOpenArtifacts(artifact); setSelectedArtifact(artifact); } }} />}
                 </div>
               </div> :
               activeTab === 'issues' ? <div className="h-full flex flex-col items-center justify-center text-muted"><Bug size={48} className="mb-4 opacity-10" /><h3 className="text-lg font-medium text-foreground">Issue Management</h3><p className="text-sm mt-1">Local and GitHub issues integration coming soon</p></div> :
               activeTab === 'interface-designer' ? <InterfaceDesigner accentColor={accentColor} isDark={themeColors.isDark} /> :
               activeTab === 'database-designer' ? <DatabaseDesigner accentColor={accentColor} isDark={themeColors.isDark} /> :
               activeTab === 'stats' ? <div className="h-full"><StatsView accentColor={accentColor} isDark={themeColors.isDark} period={statsPeriod} /></div> :
               activeTab === 'projects' ? <div className="h-full"><ProjectManagerView registry={projectRegistry} onSwitch={(p) => { switchProject(p); setActiveTab('planner'); }} onRefresh={loadRegistry} /></div> :
               activeTab === 'settings' && activeProject ? <div className="h-full"><ProjectSettingsEditor project={activeProject} workspaceRoot={workspaceRoot} onSave={() => { loadRegistry(); setActiveTab('planner'); }} onThemeChange={setCurrentTheme} onColorChange={setAccentColor} /></div> : null}
            </main>
          </Panel>

          {showRight && (
            <>
              <PanelResizeHandle className="w-1.5 bg-transparent hover:bg-zinc-500/10 active:bg-zinc-500/20 transition-all duration-150" />
              <Panel
                id="sidebar-right"
                defaultSize={250}
                minSize={150}
                onResize={(size: any) => { if (size < 150) setShowRight(false); }}
                className={cn("flex flex-col border-l transition-colors duration-300 bg-background border-border")}
              >
                {activeTab === 'setup' && <div className="flex-1 flex flex-col overflow-hidden"><AgentInteraction id="setup-chat" context="setup" interactionMode={interactionMode} setInteractionMode={(m: any) => setInteractionMode(m)} accentColor={accentColor} isDark={themeColors.isDark} activeAgents={activeAgents} onCancelCommand={handleCancelCommand} onSendMessage={(val: string) => handleSendMessage(val, 'setup')} /></div>}
                {activeTab === 'planner' && <div className="flex-1 flex flex-col overflow-hidden"><AgentInteraction id="planner-chat" context="planner" interactionMode={interactionMode} setInteractionMode={(m: any) => setInteractionMode(m)} accentColor={accentColor} isDark={themeColors.isDark} activeAgents={activeAgents} onCancelCommand={handleCancelCommand} onSendMessage={(val: string) => handleSendMessage(val, 'planner')} /></div>}
                {activeTab === 'issues' && <div className="flex-1 flex flex-col overflow-hidden"><AgentInteraction id="issues-chat" context="issues" interactionMode={interactionMode} setInteractionMode={(m: any) => setInteractionMode(m)} accentColor={accentColor} isDark={themeColors.isDark} activeAgents={activeAgents} onCancelCommand={handleCancelCommand} onSendMessage={(val: string) => handleSendMessage(val, 'issues')} /></div>}
                {activeTab === 'interface-designer' && <div className="flex-1 flex flex-col overflow-hidden"><AgentInteraction id="interface-designer-chat" context="interface" interactionMode={interactionMode} setInteractionMode={(m: any) => setInteractionMode(m)} accentColor={accentColor} isDark={themeColors.isDark} activeAgents={activeAgents} onCancelCommand={handleCancelCommand} onSendMessage={(val: string) => handleSendMessage(val, 'interface')} /></div>}
                {activeTab === 'database-designer' && <div className="flex-1 flex flex-col overflow-hidden"><AgentInteraction id="database-designer-chat" context="database" interactionMode={interactionMode} setInteractionMode={(m: any) => setInteractionMode(m)} accentColor={accentColor} isDark={themeColors.isDark} activeAgents={activeAgents} onCancelCommand={handleCancelCommand} onSendMessage={(val: string) => handleSendMessage(val, 'database')} /></div>}
                {showTerminal && (
                  <div className="h-1/3 border-t border-border/50">
                    <TerminalOutputView accentColor={accentColor} />
                  </div>
                )}
                {activeTab !== 'setup' && activeTab !== 'planner' && activeTab !== 'issues' && activeTab !== 'interface-designer' && activeTab !== 'database-designer' && (
                  <div className="flex-1 flex items-center justify-center p-8 text-center text-muted">
                    <div><MessageSquare size={32} className="mx-auto mb-4 opacity-10" /><p className="text-xs font-medium uppercase tracking-widest opacity-40">Agent chat hidden</p><p className="text-[10px] mt-2 leading-relaxed">Agent interaction is currently only available in Setup, Planner, Issues, Interface and Database views.</p></div>
                  </div>
                )}
              </Panel>
            </>
          )}
        </PanelGroup>
      </div>
      <UnifiedLogMonitor accentColor={accentColor} isDark={themeColors.isDark} />
    </div>
  );
};

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  accentColor: string;
  isDark: boolean;
}

const TabButton: React.FC<TabButtonProps> = ({ active, onClick, icon, label, accentColor, isDark }) => (
  <button onClick={onClick} className={cn("flex items-center gap-2 px-3 py-2 transition-all text-[10px] font-bold uppercase tracking-widest border-b-2", active ? cn("text-foreground", isDark ? "bg-zinc-800/50" : "bg-zinc-200/50") : cn("border-transparent text-muted hover:text-foreground", isDark ? "hover:bg-zinc-800/30" : "hover:bg-zinc-200/30"))} style={active ? { borderBottomColor: accentColor } : {}}>
    <div style={active ? { color: accentColor } : {}}>{icon}</div>
    <span>{label}</span>
  </button>
);

export default App;

import React, { useState, useEffect, useRef, useMemo } from 'react';
import Ansi from 'ansi-to-react';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle, useDefaultLayout } from 'react-resizable-panels';
import { 
  MessageSquare, 
  Files, 
  Activity, 
  PlayCircle, 
  TestTube, 
  LayoutDashboard,
  ChevronLeft,
  ChevronRight,
  Terminal,
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
  BarChart3
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
import { PlannerBoard } from './components/PlannerBoard';
import { PlannerGraph } from './components/PlannerGraph';
import { UnifiedLogMonitor } from './components/UnifiedLogMonitor';
import { ConfigForm } from './components/ConfigForm';
import { EnvEditor } from './components/EnvEditor';
import { StatsView } from './components/StatsView';

/*
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'ui-sans-serif, system-ui, sans-serif',
});
*/

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const Accordion = ({ 
  title, 
  children, 
  defaultOpen = true,
  icon: Icon
}: { 
  title: string, 
  children: React.ReactNode, 
  defaultOpen?: boolean,
  icon?: any
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-zinc-800/50 last:border-0">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-zinc-800/30 transition-colors group"
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon size={14} className={cn("text-muted group-hover:text-foreground", isOpen && "text-foreground")} />}
          <span className={cn("text-[10px] font-bold uppercase tracking-widest transition-colors", 
            isOpen ? "text-foreground" : "text-muted group-hover:text-foreground"
          )}>
            {title}
          </span>
        </div>
        <ChevronDown size={14} className={cn("text-muted transition-transform duration-200", isOpen && "rotate-180")} />
      </button>
      {isOpen && (
        <div className="px-2 pb-4">
          {children}
        </div>
      )}
    </div>
  );
};

type Tab = 'planner' | 'issues' | 'projects' | 'settings' | 'env' | 'stats';

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
  description: string;
  last_active: string;
  metadata?: Record<string, any>;
  secrets?: Record<string, string>;
  theme?: ThemeMode;
  color?: string;
}

interface ProjectRegistry {
  projects: Project[];
  last_active_project_id: string | null;
}

interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

interface Message {
  role: 'Architect' | 'PM' | 'User';
  content: string;
}

interface AgentProcess {
  pid: number;
  command: string;
  chat_id: string | null;
  tracked: boolean;
}

interface Artifact {
  name: string;
  path: string;
  type: 'prd' | 'spec' | 'issue';
  status?: string;
  owner?: string;
  lastUpdated?: string;
  relPath?: string;
  id?: string;
}

interface TreeItem {
  name: string;
  path: string;
  is_dir: boolean;
  children?: TreeItem[];
  artifact?: Artifact;
  type?: 'prd' | 'spec' | 'issue';
}

// --- Components ---

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
  const [name, setName] = useState(project.name);
  const [path, setPath] = useState(project.path);
  const [githubUrl, setGithubUrl] = useState(project.metadata?.github_url || '');
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
      // 1. Save config.json
      const configPath = `${workspaceRoot}/implementation/config.json`;
      const finalConfig = JSON.stringify(config, null, 2);
      await invoke('write_file_content', { path: configPath, content: finalConfig });

      // 2. Save project settings (theme and color) in registry
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
                        ? "bg-zinc-800 border-zinc-600 text-foreground" 
                        : "bg-zinc-950/50 border-zinc-800/50 text-muted hover:text-foreground hover:bg-zinc-900"
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

        {activeSubTab === 'config' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
            <div className="lg:col-span-1 space-y-6">
              <section className="bg-panel/50 border border-border/50 rounded-2xl p-6">
                <h3 className="text-xs font-bold text-muted flex items-center gap-2 uppercase tracking-widest mb-4">
                  <Activity size={16} />
                  Project Info
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-[10px] text-muted font-bold uppercase tracking-widest mb-1.5 block">Project Name</label>
                    <input 
                      type="text" 
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent text-foreground"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted font-bold uppercase tracking-widest mb-1.5 block">Local Path</label>
                    <input 
                      type="text" 
                      value={path}
                      onChange={(e) => setPath(e.target.value)}
                      className="w-full bg-input border border-border rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-accent text-muted"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted font-bold uppercase tracking-widest mb-1.5 block">GitHub URL</label>
                    <input 
                      type="text" 
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                      className="w-full bg-input border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent text-foreground"
                    />
                  </div>
                </div>
              </section>
            </div>

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

const VibeSidebar = ({ root, onSelect, selectedPath, accentColor }: { root: string, onSelect: (artifact: Artifact) => void, selectedPath?: string, accentColor?: string }) => {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [prdTree, setPrdTree] = useState<TreeItem[]>([]);
  const [specTree, setSpecTree] = useState<TreeItem[]>([]);
  const [issueTree, setIssueTree] = useState<TreeItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (root) loadArtifacts();
  }, [root]);

  const loadArtifacts = async () => {
    try {
      const all: Artifact[] = [];
      const scan = async (dir: string, type: 'prd' | 'spec' | 'issue'): Promise<TreeItem[]> => {
        const items: TreeItem[] = [];
        try {
          const entries = await invoke<FileEntry[]>('list_directory', { path: dir });
          for (const f of entries) {
            if (f.is_dir) {
              const children = await scan(f.path, type);
              if (children.length > 0) {
                items.push({
                  name: f.name,
                  path: f.path,
                  is_dir: true,
                  children: children.sort((a, b) => (a.is_dir === b.is_dir ? a.name.localeCompare(b.name) : a.is_dir ? -1 : 1))
                });
              }
            } else if (f.name.endsWith('.md') || f.name.endsWith('.yaml')) {
              let artifactType = type;
              const artifact: Artifact = { 
                name: f.name, 
                path: f.path, 
                type: artifactType, 
                relPath: f.path.replace(root, '')
              };
              all.push(artifact);
              items.push({ name: f.name, path: f.path, is_dir: false, artifact: artifact, type: artifactType });
            }
          }
        } catch (e) {}
        return items;
      };

      const [prd, spec, issue] = await Promise.all([
        scan(`${root}/product`, 'prd'),
        scan(`${root}/implementation`, 'spec'),
        scan(`${root}/issues`, 'issue'),
      ]);

      setArtifacts(all);
      setPrdTree(prd);
      setSpecTree(spec);
      setIssueTree(issue);
    } catch (err) {}
  };

  const filteredArtifacts = useMemo(() => {
    if (!searchQuery) return null;
    return artifacts.filter(a => 
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.relPath?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [artifacts, searchQuery]);

  return (
    <div className="flex flex-col gap-4">
      <div className="relative px-2">
        <Search className="absolute left-4 top-2.5 text-muted" size={12} />
        <input 
          type="text" 
          placeholder="Search..." 
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-input border border-border rounded-md py-1.5 pl-8 pr-3 text-[10px] focus:outline-none focus:ring-1 focus:ring-accent/50 transition-colors"
        />
      </div>
      <div className="space-y-4 max-h-[60vh] overflow-y-auto no-scrollbar px-1">
        {filteredArtifacts ? (
          <div className="space-y-1">
            {filteredArtifacts.map(artifact => (
              <button
                key={artifact.path}
                onClick={() => onSelect(artifact)}
                className={cn(
                  "w-full text-left px-2 py-1.5 rounded text-xs transition-colors truncate flex items-center gap-2",
                  selectedPath === artifact.path 
                    ? "bg-zinc-800/50 border shadow-sm font-bold" 
                    : "text-muted hover:text-foreground hover:bg-zinc-800/20"
                )}
                style={selectedPath === artifact.path ? { borderColor: `${accentColor}40`, color: accentColor } : {}}
              >
                {artifact.type === 'prd' ? <FileText size={14} className="text-purple-500" /> :
                 artifact.type === 'spec' ? <Database size={14} className="text-accent" /> :
                 <AlertCircle size={14} className="text-emerald-500" />}
                <span className="truncate">{artifact.name}</span>
              </button>
            ))}
          </div>
        ) : (
          <>
            <div>
              <div className="text-[9px] font-bold uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5 text-muted">
                <div className="w-1 h-1 rounded-full bg-purple-500" />
                Product (PRDs)
              </div>
              <SidebarTree items={prdTree} selectedPath={selectedPath} onSelect={onSelect} accentColor={accentColor} />
            </div>
            <div>
              <div className="text-[9px] font-bold uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5 text-muted">
                <div className="w-1 h-1 rounded-full bg-accent" />
                System Specs
              </div>
              <SidebarTree items={specTree} selectedPath={selectedPath} onSelect={onSelect} accentColor={accentColor} />
            </div>
            <div>
              <div className="text-[9px] font-bold uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5 text-muted">
                <div className="w-1 h-1 rounded-full bg-emerald-500" />
                Issues
              </div>
              <SidebarTree items={issueTree} selectedPath={selectedPath} onSelect={onSelect} accentColor={accentColor} />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const TerminalOutputView = () => {
  const [terminalOutput, setTerminalOutput] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    invoke<string[]>('get_terminal_buffer', { session: 'main' })
      .then(setTerminalOutput);

    const unlisten = listen('log-line', (event: any) => {
      setTerminalOutput(prev => [...prev, event.payload as string].slice(-1000));
    });

    return () => { unlisten.then(f => f()); };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [terminalOutput]);

  return (
      <div ref={scrollRef} className="h-full overflow-y-auto space-y-0.5 scrollbar-none">
      {terminalOutput.map((line, i) => (
        <div key={i} className="whitespace-pre-wrap break-all leading-relaxed text-muted opacity-80">
          <Ansi>{line}</Ansi>
        </div>
      ))}
      <div className="inline-block w-1.5 h-3 bg-muted/30 ml-1 animate-pulse" />
    </div>
  );
};

const SidebarTree = ({ 
  items, 
  level = 0, 
  selectedPath, 
  onSelect,
  accentColor
}: { 
  items: TreeItem[], 
  level?: number, 
  selectedPath?: string, 
  onSelect: (artifact: Artifact) => void,
  accentColor?: string
}) => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggle = (path: string) => {
    setExpanded(prev => ({ ...prev, [path]: !prev[path] }));
  };

  return (
    <div className="space-y-0.5">
      {items.map(item => (
        <div key={item.path}>
          {item.is_dir ? (
            <div>
              <button
                onClick={() => toggle(item.path)}
                className="w-full text-left px-2 py-1.5 rounded text-xs transition-colors flex items-center gap-1.5 font-bold text-muted hover:text-foreground hover:bg-zinc-800/20"
                style={{ paddingLeft: `${level * 12 + 8}px` }}
              >
                {expanded[item.path] ? <ChevronRight size={12} className="rotate-90" /> : <ChevronRight size={12} />}
                <Folder size={14} className="text-muted" />
                <span className="truncate">{item.name}</span>
              </button>
              {expanded[item.path] && item.children && (
                <SidebarTree 
                  items={item.children} 
                  level={level + 1} 
                  selectedPath={selectedPath} 
                  onSelect={onSelect} 
                  accentColor={accentColor}
                />
              )}
            </div>
          ) : (
            item.artifact && (
              <button
                onClick={() => onSelect(item.artifact!)}
                className={cn(
                  "w-full text-left px-2 py-1.5 rounded text-xs transition-colors truncate flex items-center gap-2",
                  selectedPath === item.path 
                    ? "bg-zinc-800/50 border shadow-sm font-bold" 
                    : "text-muted hover:text-foreground hover:bg-zinc-800/20"
                )}
                style={{ 
                  paddingLeft: `${level * 12 + 24}px`,
                  ...(selectedPath === item.path ? { borderColor: `${accentColor}40`, color: accentColor } : {})
                }}
              >
                {item.artifact.type === 'prd' ? <FileText size={14} className="text-purple-500" /> :
                 item.artifact.type === 'spec' ? <Database size={14} className="text-accent" /> :
                 <AlertCircle size={14} className="text-emerald-500" />}
                <span className="truncate">{item.name}</span>
              </button>
            )
          )}
        </div>
      ))}
    </div>
  );
};

// --- Main App ---

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
                    Last active: {new Date(project.last_active).toLocaleString()}
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
  const [activeTab, setActiveTab] = useState<Tab>('planner');
  const [workspaceRoot, setWorkspaceRoot] = useState<string>('');
  const [activeAgents, setActiveAgents] = useState<AgentProcess[]>([]);
  const [totalCost, setTotalCost] = useState<number>(0);
  const [projectRegistry, setProjectRegistry] = useState<ProjectRegistry>({ projects: [], last_active_project_id: null });
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'Architect',
      content: "Hello! I am the Architect agent. How can I help you today?"
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [serverStatus, setServerStatus] = useState<{ phase: string, status: string, progress: number } | null>(null);
  const [currentTheme, setCurrentTheme] = useState<ThemeMode>('night');
  const [accentColor, setAccentColor] = useState('#3b82f6');
  const [customThemeColors, setCustomThemeColors] = useState<Record<ThemeMode, ThemeColors>>(DEFAULT_THEMES);

  useEffect(() => {
    invoke('emit_log', { level: 'INFO', source: 'UI', message: `Tab changed to: ${activeTab}`, data: null }).catch(() => {});
  }, [activeTab]);

  const themeColors = useMemo(() => {
    return customThemeColors[currentTheme];
  }, [customThemeColors, currentTheme]);

  const loadRegistry = async () => {
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
  };

  const switchProject = async (project: Project) => {
    try {
      await invoke('emit_log', { level: 'INFO', source: 'UI', message: `Switching to project: ${project.name}`, data: null });
      await invoke('set_workspace_root', { path: project.path });
      setWorkspaceRoot(project.path);
      await loadRegistry();
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    invoke<string>('get_workspace_root')
      .then(setWorkspaceRoot)
      .catch(console.error);
    
    loadRegistry();
    
    const unlistenServer = listen('vibe-server-event', (event: any) => {
      const payload = event.payload;
      if (payload.type === 'prompt') {
        setPendingPrompt(payload.message);
      } else if (payload.type === 'status') {
        setServerStatus({
          phase: payload.phase,
          status: payload.status,
          progress: payload.progress
        });
      } else if (payload.type === 'result') {
        setPendingPrompt(null);
        setServerStatus(null);
      } else if (payload.type === 'error') {
        setMessages(prev => [...prev, {
          role: 'Architect',
          content: `❌ **Error**: ${payload.message}\n\n\`\`\`\n${payload.traceback || ''}\n\`\`\``
        }]);
      }
    });

    const interval = setInterval(() => {
      invoke<AgentProcess[]>('get_active_agents')
        .then(setActiveAgents)
        .catch(console.error);
      
      invoke<number>('get_total_cost')
        .then(setTotalCost)
        .catch(console.error);
    }, 3000);
    
    return () => {
      clearInterval(interval);
      unlistenServer.then(f => f());
    };
  }, []);

  const handlePromptSubmit = async () => {
    if (!inputValue.trim()) return;
    const val = inputValue.trim();
    setMessages(prev => [...prev, { role: 'User', content: val }]);
    setInputValue('');
    setPendingPrompt(null);
    try {
      await invoke('send_vibe_input', { input: val });
    } catch (e) {
      console.error('Error sending prompt response:', e);
    }
  };

  const handleCancelCommand = async (pid?: number) => {
    try {
      await invoke('send_vibe_input', { input: JSON.stringify({ type: 'cancel' }) });
    } catch (e) {
      if (pid) {
        await invoke('run_vibe_command', { command: 'kill', args: [pid.toString()] });
      }
    }
  };

  const handleSendMessage = () => {
    if (pendingPrompt) {
      handlePromptSubmit();
      return;
    }
    if (!inputValue.trim()) return;
    
    const content = inputValue.trim();
    setMessages(prev => [...prev, { role: 'User', content }]);
    setInputValue('');

    if (content.startsWith('/')) {
      const cmd = content.slice(1);
      const [base, ...args] = cmd.split(' ');
      invoke('run_vibe_command', { command: base, args })
        .catch(err => {
          setMessages(prev => [...prev, { 
            role: 'Architect', 
            content: `Error running command \`${cmd}\`: ${err}` 
          }]);
        });
    }
  };

  const [plannerView, setPlannerView] = useState<'board' | 'graph'>('board');

  const cycleTheme = () => {
    const modes: ThemeMode[] = ['night', 'day', 'morning', 'sunset'];
    const currentIndex = modes.indexOf(currentTheme);
    const nextIndex = (currentIndex + 1) % modes.length;
    setCurrentTheme(modes[nextIndex]);
  };

  const activeProject = useMemo(() => {
    return projectRegistry.projects.find(p => p.id === projectRegistry.last_active_project_id);
  }, [projectRegistry]);

  const {
    defaultLayout,
    onLayoutChanged,
  } = useDefaultLayout({
    id: "vibe-layout-v2",
    storage: localStorage,
  });

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
      {/* Global Header */}
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
          <div className="flex items-center gap-1 px-1 rounded-md border h-10 bg-panel border-border">
            <TabButton 
              active={activeTab === 'planner'} 
              onClick={() => setActiveTab('planner')}
              icon={<Kanban size={14} />}
              label="Planner"
              accentColor={accentColor}
            />
            <TabButton 
              active={activeTab === 'issues'} 
              onClick={() => setActiveTab('issues')}
              icon={<Bug size={14} />}
              label="Issues"
              accentColor={accentColor}
            />
            <TabButton 
              active={activeTab === 'stats'} 
              onClick={() => setActiveTab('stats')}
              icon={<BarChart3 size={14} />}
              label="Stats"
              accentColor={accentColor}
            />
            <TabButton 
              active={activeTab === 'projects'} 
              onClick={() => setActiveTab('projects')}
              icon={<LayoutDashboard size={14} />}
              label="Projects"
              accentColor={accentColor}
            />
          </div>

          <div className="flex items-center gap-2 px-2 py-1 rounded bg-panel border border-border">
            <div className={cn("w-1.5 h-1.5 rounded-full animate-pulse", activeAgents.length > 0 ? "bg-green-500" : "bg-muted")} />
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
              {activeAgents.length > 0 ? 'Working' : 'Idle'}
            </span>
          </div>
          
          <button 
            onClick={cycleTheme}
            className="p-1.5 rounded-md hover:bg-panel text-muted hover:text-foreground transition-colors flex items-center justify-center"
            title={`Switch Theme (Current: ${currentTheme})`}
          >
            {currentTheme === 'night' && <Moon size={18} />}
            {currentTheme === 'day' && <Sun size={18} />}
            {currentTheme === 'morning' && <Sunrise size={18} />}
            {currentTheme === 'sunset' && <Sunset size={18} />}
          </button>

          <button 
            onClick={() => setActiveTab('settings')}
            className={cn(
              "p-1.5 rounded-md transition-colors",
              activeTab === 'settings' ? "bg-accent text-white" : "hover:bg-panel text-muted hover:text-foreground"
            )}
            style={activeTab === 'settings' ? { backgroundColor: accentColor } : {}}
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      {activeTab === 'projects' || (activeTab === 'settings' && !activeProject) ? (
        <div className="flex-1 overflow-y-auto p-8">
          <ProjectManagerView 
            registry={projectRegistry} 
            onSwitch={(p) => {
              switchProject(p);
              setActiveTab('planner');
            }} 
            onRefresh={loadRegistry} 
          />
        </div>
      ) : activeTab === 'settings' && activeProject ? (
        <div className="flex-1 overflow-y-auto">
          <ProjectSettingsEditor 
            project={activeProject}
            workspaceRoot={workspaceRoot}
            onSave={() => {
              loadRegistry();
              setActiveTab('planner');
            }}
            onThemeChange={setCurrentTheme}
            onColorChange={setAccentColor}
          />
        </div>
      ) : (
        <PanelGroup orientation="horizontal" onLayoutChanged={onLayoutChanged} defaultLayout={defaultLayout}>
        {/* Left Pane: Project Pulse */}
        <Panel id="sidebar-left" defaultSize={200} minSize={200} className="flex flex-col border-r shadow-sm transition-colors duration-300 bg-background border-border">
          <div className="flex-1 overflow-y-auto no-scrollbar">
            <Accordion title="Projects" icon={LayoutDashboard} defaultOpen={false}>
              <div className="space-y-1">
                {projectRegistry.projects.map(p => (
                  <button
                    key={p.id}
                    onClick={() => switchProject(p)}
                    className={cn(
                      "w-full text-left px-2 py-1.5 rounded text-[11px] transition-colors truncate flex items-center gap-2",
                      projectRegistry.last_active_project_id === p.id 
                        ? "bg-zinc-800/20 border shadow-sm" 
                        : "text-muted hover:text-foreground hover:bg-zinc-800/10"
                    )}
                    style={projectRegistry.last_active_project_id === p.id ? { borderColor: `${accentColor}40`, color: accentColor } : {}}
                  >
                    <Folder size={12} className={projectRegistry.last_active_project_id === p.id ? "" : "text-muted"} style={projectRegistry.last_active_project_id === p.id ? { color: accentColor } : {}} />
                    <span className="truncate">{p.name}</span>
                  </button>
                ))}
              </div>
            </Accordion>

            <Accordion title="Vibe Explorer (PRDs)" icon={Files}>
              <div className="mt-2">
                <VibeSidebar root={workspaceRoot} onSelect={(artifact) => {
                  setSelectedArtifact(artifact);
                }} selectedPath={selectedArtifact?.path} accentColor={accentColor} currentTheme={currentTheme} />
              </div>
            </Accordion>

            <Accordion title="Properties" icon={Tag}>
              {selectedArtifact ? (
                <div className="space-y-3 p-1">
                  <div>
                    <div className="text-[9px] font-bold uppercase tracking-widest mb-1 text-muted">Name</div>
                    <div className="text-xs truncate font-medium">{selectedArtifact.name}</div>
                  </div>
                  <div>
                    <div className="text-[9px] font-bold uppercase tracking-widest mb-1 text-muted">Status</div>
                    <div className="text-xs">
                      <span className="px-1.5 py-0.5 rounded border text-[10px] font-bold bg-panel border-border">
                        {selectedArtifact.status || 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] font-bold uppercase tracking-widest mb-1 text-muted">Path</div>
                    <div className="text-[10px] font-mono break-all leading-tight text-muted">{selectedArtifact.relPath}</div>
                  </div>
                </div>
              ) : (
                <div className="text-[10px] italic text-center py-4 text-muted">No item selected</div>
              )}
            </Accordion>
          </div>

          <div className="p-4 border-t transition-colors duration-300 bg-panel border-border">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 text-muted">
                <Coins size={12} className="text-amber-500/70" />
                Cost Tracking
              </div>
            </div>
            <div className="rounded-lg p-3 border shadow-inner transition-colors duration-300 bg-background border-border">
              <div className="text-lg font-bold">${totalCost.toFixed(4)}</div>
              <div className="text-[9px] mt-0.5 uppercase font-medium text-muted">Estimated Usage</div>
            </div>
          </div>
        </Panel>

        <PanelResizeHandle className="w-1 bg-transparent hover:bg-accent/20 transition-colors" />

        {/* Center Pane: Main Content */}
        <Panel id="main-content" minSize={400} className="flex flex-col min-w-0">
          <main className="flex-1 overflow-y-auto relative p-6 no-scrollbar">
            {activeTab === 'planner' && (
              <div className="h-full flex flex-col gap-6 relative">
                <div className="flex items-center justify-between shrink-0">
                  <div>
                    <h2 className="text-2xl font-bold text-foreground">Project Planner</h2>
                    <p className="text-sm text-muted mt-1">Manage PRDs and track dependencies</p>
                  </div>
                  <div className="flex bg-panel border border-border rounded-lg p-1">
                    <button 
                      onClick={() => setPlannerView('board')}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all",
                        plannerView === 'board' ? "bg-zinc-800 text-accent shadow-sm" : "text-muted hover:text-foreground"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Kanban size={12} />
                        Board
                      </div>
                    </button>
                    <button 
                      onClick={() => setPlannerView('graph')}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all",
                        plannerView === 'graph' ? "bg-zinc-800 text-accent shadow-sm" : "text-muted hover:text-foreground"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Network size={12} />
                        Graph
                      </div>
                    </button>
                  </div>
                </div>


                <div className="flex-1 min-h-0">
                  {plannerView === 'board' ? (
                    <PlannerBoard 
                      workspaceRoot={workspaceRoot} 
                      onSelectPRD={(prd) => {
                        setSelectedArtifact({
                          id: prd.id,
                          name: prd.filename,
                          path: prd.path,
                          type: 'prd',
                          status: prd.status,
                          owner: prd.owner,
                          relPath: prd.path.replace(workspaceRoot, '')
                        });
                      }}
                      onRefresh={loadRegistry}
                      accentColor={accentColor}
                      isDark={themeColors.isDark}
                    />
                  ) : (
                    <PlannerGraph 
                      workspaceRoot={workspaceRoot}
                      onSelectPRD={async (id) => {
                         // Find PRD info
                         const entries = await invoke<any[]>('list_directory', { path: `${workspaceRoot}/product/in_progress` });
                         const entry = entries.find(e => e.name.includes(id));
                         if (entry) {
                            setSelectedArtifact({
                              id: id,
                              name: entry.name,
                              path: entry.path,
                              type: 'prd',
                              relPath: entry.path.replace(workspaceRoot, '')
                            });
                         }
                      }}
                    />
                  )}
                </div>

                <div className="shrink-0 -mx-6 -mb-6 mt-4">
                  <UnifiedLogMonitor accentColor={accentColor} />
                </div>
              </div>
            )}
            {activeTab === 'issues' && (
              <div className="h-full flex flex-col items-center justify-center text-muted">
                <Bug size={48} className="mb-4 opacity-10" />
                <h3 className="text-lg font-medium text-foreground">Issue Management</h3>
                <p className="text-sm mt-1">Local and GitHub issues integration coming soon</p>
              </div>
            )}
            {activeTab === 'stats' && (
              <div className="h-full overflow-y-auto">
                <StatsView 
                  accentColor={accentColor} 
                />
              </div>
            )}

          </main>
        </Panel>

        <PanelResizeHandle className="w-1 bg-transparent hover:bg-accent/20 transition-colors" />

        {/* Right Pane: AI / Interaction */}
        <Panel id="sidebar-right" defaultSize={300} minSize={300} className="flex flex-col border-l transition-colors duration-300 bg-background border-border">
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="p-4 border-b flex items-center justify-between transition-colors duration-300 bg-panel border-border">
              <div className="flex items-center gap-2 font-semibold">
                <MessageSquare size={16} style={{ color: accentColor }} />
                <span className="text-xs uppercase tracking-widest font-bold">Agent Interaction</span>
              </div>
              <div className="flex gap-1">
                <button onClick={() => setMessages([])} className="p-1.5 rounded transition-colors text-muted hover:text-red-400 hover:bg-zinc-800/20" title="Clear Chat">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-zinc-800">
              {messages.map((msg, i) => (
                <div key={i} className={cn(
                  "rounded-lg p-3 border shadow-sm transition-all duration-300",
                  msg.role === 'User' ? "bg-panel border-border ml-4" : "bg-panel border-border mr-4 shadow-md"
                )}>
                  <div className={cn(
                    "text-[10px] font-bold mb-1 uppercase tracking-wider",
                    msg.role === 'Architect' ? "text-accent" : msg.role === 'PM' ? "text-purple-500" : "text-emerald-500"
                  )} style={msg.role === 'User' ? { color: accentColor } : {}}>
                    {msg.role}
                  </div>
                  <div className={cn("text-sm prose max-w-none transition-colors duration-300", themeColors.isDark ? "prose-invert" : "prose-zinc")}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                </div>
              ))}
              
              {activeAgents.length > 0 && (
                <div className="pt-4 border-t transition-colors duration-300 border-border">
                  <div className="text-[10px] font-bold uppercase tracking-widest mb-2 px-1 text-muted">Active Processes</div>
                  <div className="space-y-2">
                    {activeAgents.map(agent => (
                      <div key={agent.pid} className="flex items-center justify-between border rounded px-2 py-1.5 shadow-sm transition-colors duration-300 bg-panel border-border">
                        <div className="flex items-center gap-2 overflow-hidden">
                          <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: accentColor }} />
                          <span className="text-[10px] font-mono truncate font-bold" style={{ color: accentColor }}>{agent.command}</span>
                        </div>
                        <button 
                          onClick={() => handleCancelCommand(agent.pid)}
                          className="p-0.5 rounded transition-colors text-muted hover:text-red-400"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t transition-colors duration-300 bg-panel border-border">
              {pendingPrompt && (
                <div className="mb-4 p-3 bg-accent/10 border border-accent/30 rounded-lg shadow-sm">
                  <div className="text-[10px] font-bold text-accent uppercase tracking-widest mb-1">Input Required</div>
                  <div className="text-xs mb-2 font-medium">{pendingPrompt}</div>
                </div>
              )}
              
              {serverStatus && (
                <div className="mb-4 p-3 border rounded-lg transition-colors duration-300 shadow-sm bg-background border-border">
                  <div className="flex justify-between items-center mb-1.5">
                    <div className="text-[9px] font-bold uppercase tracking-widest text-muted">{serverStatus.phase}</div>
                    <div className="text-[9px] font-mono font-bold text-muted">{serverStatus.progress}%</div>
                  </div>
                  <div className="w-full bg-zinc-950/10 rounded-full h-1.5 overflow-hidden">
                    <div 
                      className="h-full transition-all duration-500" 
                      style={{ width: `${serverStatus.progress}%`, backgroundColor: accentColor }} 
                    />
                  </div>
                </div>
              )}

              <div className="relative flex gap-2">
                <input 
                  type="text" 
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Ask the Architect..."
                  className="flex-1 border rounded-md py-2 px-3 text-xs focus:outline-none focus:ring-2 transition-all duration-300 bg-input border-border focus:ring-accent/50"
                />
                <button 
                  onClick={handleSendMessage}
                  className="p-2 text-white rounded-md transition-all shadow-lg active:scale-95"
                  style={{ backgroundColor: accentColor }}
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </div>

          <div className="h-48 border-t p-2 overflow-hidden flex flex-col transition-colors duration-300 bg-background border-border">
            <div className="flex items-center gap-2 px-2 py-1 text-[9px] font-bold uppercase tracking-widest mb-1 text-muted">
              <Terminal size={10} />
              Command Output
            </div>
            <div className="flex-1 overflow-y-auto font-mono text-[10px] p-2 rounded scrollbar-none transition-colors duration-300 bg-panel border-border border shadow-inner">
              <TerminalOutputView />
            </div>
          </div>
        </Panel>
      </PanelGroup>
      )}
    </div>
  );
};

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  accentColor: string;
}

const TabButton: React.FC<TabButtonProps> = ({ active, onClick, icon, label, accentColor }) => (
  <button 
    onClick={onClick}
    className={cn(
      "flex items-center gap-2 px-3 py-2 transition-all text-[10px] font-bold uppercase tracking-widest border-b-2",
      active 
        ? "text-foreground bg-zinc-800/50" 
        : "border-transparent text-muted hover:text-foreground hover:bg-zinc-800/30"
    )}
    style={active ? { borderBottomColor: accentColor } : {}}
  >
    <div style={active ? { color: accentColor } : {}}>{icon}</div>
    <span>{label}</span>
  </button>
);

export default App;

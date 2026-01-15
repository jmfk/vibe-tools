import React, { useState, useEffect, useRef, useMemo } from 'react';
import Ansi from 'ansi-to-react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
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
  Cpu,
  Coins,
  ChevronDown,
  Network
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import yaml from 'js-yaml';
import mermaid from 'mermaid';
import { PlannerBoard } from './components/PlannerBoard';
import { PlannerGraph } from './components/PlannerGraph';
import { AgentLogMonitor } from './components/AgentLogMonitor';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'ui-sans-serif, system-ui, sans-serif',
});

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
          {Icon && <Icon size={14} className={cn("text-zinc-500 group-hover:text-zinc-300", isOpen && "text-zinc-300")} />}
          <span className={cn("text-[10px] font-bold uppercase tracking-widest transition-colors", 
            isOpen ? "text-zinc-200" : "text-zinc-500 group-hover:text-zinc-400"
          )}>
            {title}
          </span>
        </div>
        <ChevronDown size={14} className={cn("text-zinc-600 transition-transform duration-200", isOpen && "rotate-180")} />
      </button>
      {isOpen && (
        <div className="px-2 pb-4">
          {children}
        </div>
      )}
    </div>
  );
};

type Tab = 'planner' | 'create' | 'issues';

interface Project {
  id: string;
  name: string;
  path: string;
  description: string;
  last_active: string;
  metadata?: Record<string, any>;
  secrets?: Record<string, string>;
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

const VibeSidebar = ({ root, onSelect, selectedPath }: { root: string, onSelect: (artifact: Artifact) => void, selectedPath?: string }) => {
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
        <Search className="absolute left-4 top-2.5 text-zinc-600" size={12} />
        <input 
          type="text" 
          placeholder="Search..." 
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-zinc-800/50 border border-zinc-700/50 rounded-md py-1.5 pl-8 pr-3 text-[10px] focus:outline-none focus:ring-1 focus:ring-blue-500/50"
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
                    ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" 
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                )}
              >
                {artifact.type === 'prd' ? <FileText size={14} className="text-purple-500/50" /> :
                 artifact.type === 'spec' ? <Database size={14} className="text-blue-500/50" /> :
                 <AlertCircle size={14} className="text-emerald-500/50" />}
                <span className="truncate">{artifact.name}</span>
              </button>
            ))}
          </div>
        ) : (
          <>
            <div>
              <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5">
                <div className="w-1 h-1 rounded-full bg-purple-500/50" />
                Product (PRDs)
              </div>
              <SidebarTree items={prdTree} selectedPath={selectedPath} onSelect={onSelect} />
            </div>
            <div>
              <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5">
                <div className="w-1 h-1 rounded-full bg-blue-500/50" />
                System Specs
              </div>
              <SidebarTree items={specTree} selectedPath={selectedPath} onSelect={onSelect} />
            </div>
            <div>
              <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5">
                <div className="w-1 h-1 rounded-full bg-emerald-500/50" />
                Issues
              </div>
              <SidebarTree items={issueTree} selectedPath={selectedPath} onSelect={onSelect} />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const ArtifactContentView = ({ artifact, workspaceRoot }: { artifact: Artifact, workspaceRoot: string }) => {
  const [content, setContent] = useState('');
  const [yamlData, setYamlData] = useState<any>(null);
  const [markdownContent, setMarkdownContent] = useState('');
  const [showSpecSplit, setShowSpecSplit] = useState(false);

  useEffect(() => {
    if (artifact) {
      invoke<string>('read_file_content', { path: artifact.path })
        .then(raw => {
          setContent(raw);
          const match = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
          if (match) {
            try {
              setYamlData(yaml.load(match[1]));
              setMarkdownContent(match[2]);
            } catch (e) {
              setYamlData(null);
              setMarkdownContent(raw);
            }
          } else {
            setYamlData(null);
            setMarkdownContent(raw);
          }
        });
    }
  }, [artifact]);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className={cn(
              "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider",
              artifact.type === 'prd' ? "bg-purple-500/10 text-purple-400 border border-purple-500/20" :
              artifact.type === 'spec' ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" : 
              "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            )}>
              {artifact.type}
            </span>
            <span className="text-[10px] text-zinc-500 font-mono">{artifact.relPath}</span>
          </div>
          <h1 className="text-2xl font-bold text-zinc-100 mt-1">{artifact.name}</h1>
        </div>
        <button 
          onClick={() => invoke('open_in_cursor', { path: artifact.path })}
          className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-[10px] font-bold text-zinc-200 transition-colors uppercase tracking-widest"
        >
          <Eye size={14} /> Open in Cursor
        </button>
      </div>

      <FrontmatterCard data={yamlData} />

      <div className="prose prose-invert max-w-none mt-8 prose-sm prose-zinc">
        <MarkdownRenderer content={markdownContent} />
      </div>

      {artifact.type === 'issue' && <IssueTimeline content={content} />}
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
        <div key={i} className="whitespace-pre-wrap break-all leading-relaxed text-zinc-400">
          <Ansi>{line}</Ansi>
        </div>
      ))}
      <div className="inline-block w-1.5 h-3 bg-zinc-700 ml-1 animate-pulse" />
    </div>
  );
};

const SidebarTree = ({ 
  items, 
  level = 0, 
  selectedPath, 
  onSelect 
}: { 
  items: TreeItem[], 
  level?: number, 
  selectedPath?: string, 
  onSelect: (artifact: Artifact) => void 
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
                className="w-full text-left px-2 py-1.5 rounded text-xs transition-colors hover:bg-zinc-800 flex items-center gap-1.5 text-zinc-500 font-medium"
                style={{ paddingLeft: `${level * 12 + 8}px` }}
              >
                {expanded[item.path] ? <ChevronRight size={12} className="rotate-90" /> : <ChevronRight size={12} />}
                <Folder size={14} className="text-zinc-600" />
                <span className="truncate">{item.name}</span>
              </button>
              {expanded[item.path] && item.children && (
                <SidebarTree 
                  items={item.children} 
                  level={level + 1} 
                  selectedPath={selectedPath} 
                  onSelect={onSelect} 
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
                    ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" 
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                )}
                style={{ paddingLeft: `${level * 12 + 24}px` }}
              >
                {item.artifact.type === 'prd' ? <FileText size={14} className="text-purple-500/50" /> :
                 item.artifact.type === 'spec' ? <Database size={14} className="text-blue-500/50" /> :
                 <AlertCircle size={14} className="text-emerald-500/50" />}
                <span className="truncate">{item.name}</span>
              </button>
            )
          )}
        </div>
      ))}
    </div>
  );
};

const Mermaid = ({ chart }: { chart: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState('');

  useEffect(() => {
    if (chart) {
      const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
      mermaid.render(id, chart).then(({ svg }) => {
        setSvg(svg);
      }).catch(err => {
        console.error('Mermaid render error:', err);
      });
    }
  }, [chart]);

  return <div className="mermaid-container my-4 overflow-x-auto bg-zinc-900/50 p-4 rounded-lg border border-zinc-800" dangerouslySetInnerHTML={{ __html: svg }} />;
};

const MarkdownRenderer = ({ content }: { content: string }) => {
  return (
    <ReactMarkdown 
      remarkPlugins={[remarkGfm]} 
      rehypePlugins={[rehypeHighlight]}
      components={{
        code({ node, inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || '');
          if (!inline && match && match[1] === 'mermaid') {
            return <Mermaid chart={String(children).replace(/\n$/, '')} />;
          }
          return (
            <code className={className} {...props}>
              {children}
            </code>
          );
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );
};

const FrontmatterCard = ({ data }: { data: any }) => {
  if (!data) return null;
  return (
    <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-4 mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
      {Object.entries(data).map(([key, value]: [string, any]) => (
        <div key={key}>
          <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-1">{key}</div>
          <div className="text-sm text-zinc-200 font-medium">
            {typeof value === 'string' ? value : JSON.stringify(value)}
          </div>
        </div>
      ))}
    </div>
  );
};

const IssueTimeline = ({ content }: { content: string }) => {
  const lines = content.split('\n');
  const timelineItems: { date: string, text: string, type: 'investigation' | 'solution' | 'history' | 'status' }[] = [];
  
  let currentType: 'investigation' | 'solution' | 'history' | null = null;
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (trimmedLine.includes('## Investigation Notes')) currentType = 'investigation';
    else if (trimmedLine.includes('## Solution Notes')) currentType = 'solution';
    else if (trimmedLine.includes('## Implementation History')) currentType = 'history';
    else if (currentType && trimmedLine.startsWith('- [')) {
      const match = trimmedLine.match(/- \[(.*?)\] (.*)/);
      if (match) {
        timelineItems.push({ date: match[1], text: match[2], type: currentType });
      }
    } else if (currentType === 'history' && trimmedLine.startsWith('### ')) {
      const match = trimmedLine.match(/### (.*)/);
      if (match) {
        timelineItems.push({ date: match[1], text: 'Implementation update', type: 'history' });
      }
    } else if (trimmedLine.startsWith('- Agent started') || trimmedLine.startsWith('- Agent finished')) {
      const match = trimmedLine.match(/- Agent (started|finished) (.*) mode at (.*)/);
      if (match) {
        timelineItems.push({ 
          date: match[3], 
          text: `Agent ${match[1]} ${match[2]}`, 
          type: 'status' 
        });
      }
    }
  }

  if (timelineItems.length === 0) return null;

  // Sort by date if possible
  const sortedItems = [...timelineItems].sort((a, b) => {
    try {
      return new Date(a.date).getTime() - new Date(b.date).getTime();
    } catch (e) {
      return 0;
    }
  });

  return (
    <div className="mt-8 pt-8 border-t border-zinc-800">
      <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-widest mb-4">Event Timeline</h3>
      <div className="relative ml-2 border-l border-zinc-800 pl-6 space-y-6">
        {sortedItems.map((item, i) => (
          <div key={i} className="relative">
            <div className={cn(
              "absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-zinc-950",
              item.type === 'investigation' ? "bg-blue-500" : 
              item.type === 'solution' ? "bg-emerald-500" :
              item.type === 'status' ? "bg-purple-500" : "bg-zinc-500"
            )} />
            <div className="text-[10px] font-mono text-zinc-500 mb-1">{item.date}</div>
            <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-lg p-3">
              <div className={cn(
                "text-[10px] font-bold uppercase mb-1",
                item.type === 'investigation' ? "text-blue-400" : 
                item.type === 'solution' ? "text-emerald-400" :
                item.type === 'status' ? "text-purple-400" : "text-zinc-400"
              )}>
                {item.type}
              </div>
              <div className="text-sm text-zinc-300">{item.text}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const YAMLTreeView = ({ data, level = 0 }: { data: any, level?: number }) => {
  if (data === null || data === undefined) return <span className="text-zinc-500 italic">null</span>;
  
  if (typeof data !== 'object') {
    return <span className="text-blue-400">{String(data)}</span>;
  }

  if (Array.isArray(data)) {
    return (
      <div className="space-y-1">
        {data.map((item, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-zinc-600 font-mono">-</span>
            <div className="flex-1">
              <YAMLTreeView data={item} level={level + 1} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="flex flex-col">
          <div className="flex items-baseline gap-2">
            <span className="text-zinc-500 font-mono text-[10px] uppercase tracking-wider font-bold">{key}:</span>
            {typeof value !== 'object' && <YAMLTreeView data={value} />}
          </div>
          {typeof value === 'object' && value !== null && (
            <div className="ml-4 mt-1 border-l border-zinc-800 pl-4">
              <YAMLTreeView data={value} level={level + 1} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

const VibeView = ({ root }: { root: string }) => {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [prdTree, setPrdTree] = useState<TreeItem[]>([]);
  const [specTree, setSpecTree] = useState<TreeItem[]>([]);
  const [issueTree, setIssueTree] = useState<TreeItem[]>([]);
  const [content, setContent] = useState('');
  const [yamlData, setYamlData] = useState<any>(null);
  const [markdownContent, setMarkdownContent] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'active' | 'pending' | 'completed'>('all');
  const [showSpecSplit, setShowSpecSplit] = useState(false);

  useEffect(() => {
    if (root) {
      loadArtifacts();
    }
  }, [root]);

  const loadArtifacts = async () => {
    try {
      const all: Artifact[] = [];
      
      const scan = async (dir: string, type: 'prd' | 'spec' | 'issue', baseDir: string): Promise<TreeItem[]> => {
        const items: TreeItem[] = [];
        try {
          const entries = await invoke<FileEntry[]>('list_directory', { path: dir });
          for (const f of entries) {
            if (f.is_dir) {
              const children = await scan(f.path, type, baseDir);
              if (children.length > 0) {
                items.push({
                  name: f.name,
                  path: f.path,
                  is_dir: true,
                  children: children.sort((a, b) => (a.is_dir === b.is_dir ? a.name.localeCompare(b.name) : a.is_dir ? -1 : 1))
                });
              }
            } else if (f.name.endsWith('.md') || f.name.endsWith('.yaml')) {
              let status = '';
              let owner = '';
              let artifactType = type;
              let artifactId = f.name.split('-').slice(0, 2).join('-'); // Default for PRD-XXX or ISSUE-YYYY
              if (f.name.startsWith('ISSUE-')) {
                artifactId = f.name.split('-').slice(0, 5).join('-'); // ISSUE-YYYY-MM-DD-NNN
              }
              
              try {
                const raw = await invoke<string>('read_file_content', { path: f.path });
                if (f.name.endsWith('.md')) {
                  const match = raw.match(/^---\n([\s\S]*?)\n---\n/);
                  if (match) {
                    const parsed: any = yaml.load(match[1]);
                    status = parsed.status || '';
                    owner = parsed.owner || parsed.agent || '';
                    if (parsed.id) artifactId = parsed.id;
                    if (parsed.type === 'ISSUE') artifactType = 'issue';
                  }
                } else if (f.name.endsWith('.yaml')) {
                  const parsed: any = yaml.load(raw);
                  status = parsed.status || '';
                  owner = parsed.owner || '';
                  if (parsed.id) artifactId = parsed.id;
                }
              } catch (e) {}

              const artifact: Artifact = { 
                name: f.name, 
                path: f.path, 
                type: artifactType, 
                status, 
                owner,
                id: artifactId,
                relPath: f.path.replace(root, '')
              };
              
              // Only add if it matches the requested type in the scan (unless it was promoted to issue)
              if (artifactType === type || (type === 'prd' && artifactType === 'issue')) {
                all.push(artifact);
                items.push({
                  name: f.name,
                  path: f.path,
                  is_dir: false,
                  artifact: artifact,
                  type: artifactType
                });
              }
            }
          }
        } catch (e) {}
        return items;
      };

      const [prdTree, specTree, issueTreeRaw] = await Promise.all([
        scan(`${root}/product`, 'prd', `${root}/product`),
        scan(`${root}/implementation`, 'spec', `${root}/implementation`),
        scan(`${root}/issues`, 'issue', `${root}/issues`),
      ]);

      // Separate issues from PRDs for the dedicated "issue" category
      const filterTreeForType = (items: TreeItem[], type: string): TreeItem[] => {
        return items.map(item => {
          if (item.is_dir) {
            const children = filterTreeForType(item.children || [], type);
            return children.length > 0 ? { ...item, children } : null;
          }
          return item.type === type ? item : null;
        }).filter(Boolean) as TreeItem[];
      };

      setArtifacts(all);
      setPrdTree(filterTreeForType(prdTree, 'prd'));
      setSpecTree(specTree);
      setIssueTree([...filterTreeForType(prdTree, 'issue'), ...issueTreeRaw]);

    } catch (err) {
      console.error('Error loading artifacts:', err);
    }
  };

  const filteredArtifacts = useMemo(() => {
    let result = artifacts;
    
    if (searchQuery) {
      result = result.filter(a => 
        a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.relPath?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.status?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.owner?.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    if (filterType === 'active') {
      result = result.filter(a => a.type === 'issue' && a.status === 'in_progress');
    } else if (filterType === 'pending') {
      result = result.filter(a => (a.type === 'prd' || a.type === 'issue') && (a.status === 'backlog' || a.status === 'draft' || a.status === 'todo'));
    } else if (filterType === 'completed') {
      result = result.filter(a => a.status === 'completed' || a.status === 'done' || a.status === 'history');
    }

    return result;
  }, [artifacts, searchQuery, filterType]);

  useEffect(() => {
    if (selectedArtifact) {
      invoke<string>('read_file_content', { path: selectedArtifact.path })
        .then(async (raw) => {
          setContent(raw);
          if (selectedArtifact.type === 'prd' || selectedArtifact.type === 'issue') {
            const match = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
            if (match) {
              try {
                setYamlData(yaml.load(match[1]));
                setMarkdownContent(match[2]);
              } catch (e) {
                setYamlData(null);
                setMarkdownContent(raw);
              }
            } else {
              setYamlData(null);
              setMarkdownContent(raw);
            }
          } else if (selectedArtifact.type === 'spec') {
            try {
              const data = yaml.load(raw);
              setYamlData(data);
              // Try to find corresponding markdown in product/ recursively
              const baseName = selectedArtifact.name.replace('.yaml', '');
              
              const findMd = async (dir: string): Promise<string | null> => {
                const entries = await invoke<FileEntry[]>('list_directory', { path: dir });
                for (const e of entries) {
                  if (e.is_dir) {
                    const found = await findMd(e.path);
                    if (found) return found;
                  } else if (e.name === `${baseName}.md` || e.name === `${baseName}.yaml.md`) {
                    return e.path;
                  }
                }
                return null;
              };

              const prdPath = await findMd(`${root}/product`);
              if (prdPath) {
                const md = await invoke<string>('read_file_content', { path: prdPath });
                setMarkdownContent(md);
              } else {
                setMarkdownContent('');
              }
            } catch (e) {
              setYamlData(null);
            }
          }
        })
        .catch(console.error);
    }
  }, [selectedArtifact]);

  const handleOpenInCursor = () => {
    if (selectedArtifact) {
      invoke('open_in_cursor', { path: selectedArtifact.path }).catch(console.error);
    }
  };

  const runVibeAction = async (cmd: string, args: string[]) => {
    try {
      if (cmd === 'issue' && args[0] === 'status' && args[2] === 'history') {
        const id = args[1];
        const newPath = `${root}/product/history/${selectedArtifact?.name}`;
        await invoke('move_file', { from: selectedArtifact?.path, to: newPath });
        await invoke('run_vibe_command', { command: 'issue', args: ['status', id, 'done'] });
        setSelectedArtifact(null);
      } else {
        await invoke('run_vibe_command', { command: cmd, args });
      }
      setTimeout(loadArtifacts, 500);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex h-full gap-6 overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 flex flex-col gap-4 overflow-hidden">
        <div className="flex flex-col gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 text-zinc-500" size={14} />
            <input 
              type="text" 
              placeholder="Search artifacts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-md py-2 pl-9 pr-3 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex gap-1 overflow-x-auto no-scrollbar pb-1">
            {[
              { id: 'all', label: 'All', icon: <Files size={12} /> },
              { id: 'active', label: 'Active', icon: <Activity size={12} /> },
              { id: 'pending', label: 'Pending', icon: <Clock size={12} /> },
              { id: 'completed', label: 'Done', icon: <CheckCircle2 size={12} /> },
            ].map(f => (
              <button
                key={f.id}
                onClick={() => setFilterType(f.id as any)}
                className={cn(
                  "flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-medium transition-colors whitespace-nowrap border",
                  filterType === f.id 
                    ? "bg-blue-500/10 text-blue-400 border-blue-500/20" 
                    : "bg-zinc-900 text-zinc-500 border-zinc-800 hover:text-zinc-300"
                )}
              >
                {f.icon}
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-1 pr-2">
          {searchQuery || filterType !== 'all' ? (
            <div className="space-y-1">
               {filteredArtifacts.map(artifact => (
                <button
                  key={artifact.path}
                  onClick={() => setSelectedArtifact(artifact)}
                  className={cn(
                    "w-full text-left px-2 py-1.5 rounded text-xs transition-colors truncate flex items-center gap-2",
                    selectedArtifact?.path === artifact.path 
                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" 
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                  )}
                >
                  {artifact.type === 'prd' ? <FileText size={14} className="text-purple-500/50" /> :
                   artifact.type === 'spec' ? <Database size={14} className="text-blue-500/50" /> :
                   <AlertCircle size={14} className="text-emerald-500/50" />}
                  <span className="truncate">{artifact.name}</span>
                </button>
              ))}
            </div>
          ) : (
            <>
              <div className="mb-6">
                <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2 px-2">PRDs</div>
                <SidebarTree items={prdTree} selectedPath={selectedArtifact?.path} onSelect={setSelectedArtifact} />
              </div>
              <div className="mb-6">
                <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2 px-2">System Specs</div>
                <SidebarTree items={specTree} selectedPath={selectedArtifact?.path} onSelect={setSelectedArtifact} />
              </div>
              <div className="mb-6">
                <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2 px-2">Issues</div>
                <SidebarTree items={issueTree} selectedPath={selectedArtifact?.path} onSelect={setSelectedArtifact} />
              </div>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto min-w-0 bg-zinc-900/30 rounded-xl border border-zinc-800/50 p-6">
        {selectedArtifact ? (
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={cn(
                    "px-1.5 py-0.5 rounded-[4px] text-[10px] font-bold uppercase",
                    selectedArtifact.type === 'prd' ? "bg-purple-500/10 text-purple-400" :
                    selectedArtifact.type === 'spec' ? "bg-blue-500/10 text-blue-400" : "bg-emerald-500/10 text-emerald-400"
                  )}>
                    {selectedArtifact.type}
                  </span>
                  <span className="text-zinc-500 text-xs font-mono">{selectedArtifact.relPath}</span>
                </div>
                <h1 className="text-2xl font-bold text-zinc-100">{selectedArtifact.name}</h1>
              </div>
              
              <div className="flex gap-2">
                {selectedArtifact.type === 'spec' && (
                  <button 
                    onClick={() => setShowSpecSplit(!showSpecSplit)}
                    className={cn(
                      "p-2 rounded border transition-colors",
                      showSpecSplit ? "bg-blue-600 border-blue-500 text-white" : "bg-zinc-800 border-zinc-700 text-zinc-400"
                    )}
                    title="Side-by-side View"
                  >
                    <Split size={18} />
                  </button>
                )}
                <button 
                  onClick={handleOpenInCursor}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-xs font-medium text-zinc-200 transition-colors"
                >
                  Open in Cursor
                </button>
              </div>
            </div>

            <FrontmatterCard data={yamlData} />

            {selectedArtifact.type === 'issue' && (
              <div className="mb-6 flex flex-wrap gap-y-3 gap-x-6 p-4 bg-zinc-900/50 border border-zinc-800 rounded-lg">
                <div className="flex items-center gap-2">
                  <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Status:</div>
                  <select 
                    value={selectedArtifact.status}
                    onChange={(e) => runVibeAction('issue', ['status', selectedArtifact.id || '', e.target.value])}
                    className="bg-zinc-800 border border-zinc-700 rounded text-[10px] px-2 py-1 text-zinc-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {['backlog', 'in_progress', 'completed', 'history'].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Agent:</div>
                  <select 
                    value={selectedArtifact.owner}
                    onChange={(e) => runVibeAction('issue', ['assign', selectedArtifact.id || '', e.target.value])}
                    className="bg-zinc-800 border border-zinc-700 rounded text-[10px] px-2 py-1 text-zinc-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="">Unassigned</option>
                    {['Architect', 'PM', 'Developer'].map(a => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2 ml-auto">
                  <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Quick Actions:</div>
                  <button 
                    onClick={() => runVibeAction('issue', ['status', selectedArtifact.id || '', 'history'])}
                    className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-[10px] font-medium text-zinc-300 transition-colors"
                  >
                    Move to History
                  </button>
                  <button 
                    onClick={() => {
                      const prdId = prompt('Enter PRD ID to link to:');
                      if (prdId) runVibeAction('issue', ['link', selectedArtifact.id || '', prdId]);
                    }}
                    className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-[10px] font-medium text-zinc-300 transition-colors"
                  >
                    Link PRD
                  </button>
                </div>
              </div>
            )}

            {selectedArtifact.type === 'spec' && showSpecSplit ? (
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6 overflow-x-auto">
                  <YAMLTreeView data={yamlData} />
                </div>
                <div className="prose prose-invert max-w-none">
                  <MarkdownRenderer content={markdownContent || "*No documentation found in product/*"} />
                </div>
              </div>
            ) : (
              <div className="prose prose-invert max-w-none">
                {selectedArtifact.type === 'spec' ? (
                   <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-8 overflow-x-auto">
                    <YAMLTreeView data={yamlData} />
                  </div>
                ) : (
                  <MarkdownRenderer content={markdownContent} />
                )}
              </div>
            )}

            {selectedArtifact.type === 'issue' && <IssueTimeline content={content} />}
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-zinc-500">
            <div className="w-16 h-16 rounded-full bg-zinc-800/50 flex items-center justify-center mb-4">
              <Files size={32} className="text-zinc-600" />
            </div>
            <h3 className="text-lg font-medium text-zinc-300">Select an artifact to view</h3>
            <p className="text-sm mt-1">Browse PRDs, System Specs, and Issues from the sidebar</p>
          </div>
        )}
      </div>
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

      await invoke('run_vibe_command', { 
        command: 'project', 
        args: [
          'add', 
          editingProject.path, 
          '--name', editName
        ] 
      });
      
      // Since 'vibe project add' doesn't support metadata/secrets yet, 
      // we'll need to update the registry file directly from Tauri or update the CLI.
      // For now, let's assume we need to update the registry via a new Tauri command
      // because the CLI 'project add' is basic.
      
      await invoke('update_project_registry', {
        id: editingProject.id,
        name: editName,
        description: editDesc,
        githubUrl: editGithub,
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
          <h2 className="text-2xl font-bold text-zinc-100">Project Manager</h2>
          <p className="text-sm text-zinc-500 mt-1">Manage and switch between your vibe projects</p>
        </div>
        {!editingProject && (
          <div className="flex gap-2">
            <input 
              type="text" 
              placeholder="Path to project..."
              value={importPath}
              onChange={(e) => setImportPath(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 w-64"
            />
            <button 
              onClick={handleImport}
              className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md text-sm font-bold transition-colors"
            >
              Import Project
            </button>
          </div>
        )}
      </div>

      {editingProject ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-bold text-zinc-100">Edit Project: {editingProject.name}</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Name</label>
              <input 
                type="text" 
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">GitHub URL</label>
              <input 
                type="text" 
                value={editGithub}
                onChange={(e) => setEditGithub(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="col-span-2 space-y-1">
              <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Description</label>
              <input 
                type="text" 
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="col-span-2 space-y-1">
              <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Secrets (JSON)</label>
              <textarea 
                value={editSecrets}
                onChange={(e) => setEditSecrets(e.target.value)}
                rows={5}
                className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button 
              onClick={() => setEditingProject(null)}
              className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Cancel
            </button>
            <button 
              onClick={saveEdit}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md text-sm font-bold transition-colors"
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
                  ? "bg-blue-500/5 border-blue-500/30" 
                  : "bg-zinc-900/50 border-zinc-800 hover:border-zinc-700"
              )}
            >
              <div className="flex-1 min-w-0 pr-8">
                <div className="flex items-center gap-3 mb-1">
                  <h3 className="text-lg font-bold text-zinc-100 truncate">{project.name}</h3>
                  {registry.last_active_project_id === project.id && (
                    <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-[10px] font-bold uppercase tracking-wider">Active</span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-zinc-500 text-sm font-mono truncate mb-2">
                  <Folder size={14} />
                  <span>{project.path}</span>
                </div>
                {project.description && (
                  <p className="text-sm text-zinc-400 line-clamp-1">{project.description}</p>
                )}
                <div className="flex items-center gap-4 mt-3">
                  <div className="text-[10px] text-zinc-600 font-medium uppercase tracking-widest">
                    Last active: {new Date(project.last_active).toLocaleString()}
                  </div>
                  {project.metadata?.github_url && (
                    <div className="flex items-center gap-1 text-[10px] text-blue-500/70 font-medium uppercase tracking-widest">
                      <LinkIcon size={10} />
                      GitHub Linked
                    </div>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-3">
                <button 
                  onClick={() => startEditing(project)}
                  className="p-2 text-zinc-500 hover:text-zinc-200 transition-colors"
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
                      ? "bg-zinc-800 text-zinc-500 cursor-default"
                      : "bg-zinc-100 text-zinc-950 hover:bg-white"
                  )}
                >
                  {registry.last_active_project_id === project.id ? "Current" : "Switch to Project"}
                </button>
                <button 
                  onClick={() => handleRemove(project.id)}
                  className="p-2 text-zinc-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                  title="Remove from registry"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}
          
          {registry.projects.length === 0 && (
            <div className="h-64 flex flex-col items-center justify-center text-zinc-500 bg-zinc-900/30 border border-dashed border-zinc-800 rounded-xl">
               <LayoutDashboard size={48} className="mb-4 opacity-10" />
               <p className="text-lg font-medium text-zinc-400">No projects registered yet</p>
               <p className="text-sm mt-1">Import an existing project or use 'vibe init' in the CLI</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('create');
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

  const loadRegistry = async () => {
    try {
      const registry = await invoke<ProjectRegistry>('get_projects');
      setProjectRegistry(registry);
    } catch (e) {
      console.error(e);
    }
  };

  const switchProject = async (project: Project) => {
    try {
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

  const activeProject = useMemo(() => {
    return projectRegistry.projects.find(p => p.id === projectRegistry.last_active_project_id);
  }, [projectRegistry]);

  return (
    <div className="flex flex-col h-screen w-full bg-zinc-950 text-zinc-300 overflow-hidden font-sans">
      {/* Global Header */}
      <header className="h-12 border-b border-zinc-800 flex items-center justify-between px-4 bg-zinc-900/50 backdrop-blur-sm z-20">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center">
            <Cpu size={14} className="text-white" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold text-zinc-100 leading-none">{activeProject?.name || 'No Project'}</span>
            <span className="text-[10px] text-zinc-500 font-mono leading-none mt-1 truncate max-w-[200px]">{workspaceRoot || 'Not connected'}</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-2 py-1 rounded bg-zinc-800/50 border border-zinc-700/50">
            <div className={cn("w-1.5 h-1.5 rounded-full animate-pulse", activeAgents.length > 0 ? "bg-green-500" : "bg-zinc-600")} />
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">
              {activeAgents.length > 0 ? 'Working' : 'Idle'}
            </span>
          </div>
          <button className="p-1.5 hover:bg-zinc-800 rounded-md text-zinc-500 hover:text-zinc-300 transition-colors">
            <Settings size={18} />
          </button>
        </div>
      </header>

      <PanelGroup direction="horizontal" autoSaveId="vibe-layout-v1">
        {/* Left Pane: Project Pulse */}
        <Panel defaultSize={20} minSize={15} className="flex flex-col bg-zinc-900/20 border-r border-zinc-800">
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
                        ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" 
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                    )}
                  >
                    <Folder size={12} className={projectRegistry.last_active_project_id === p.id ? "text-blue-400" : "text-zinc-600"} />
                    <span className="truncate">{p.name}</span>
                  </button>
                ))}
              </div>
            </Accordion>

            <Accordion title="Vibe Explorer (PRDs)" icon={Files}>
              <div className="mt-2">
                <VibeSidebar root={workspaceRoot} onSelect={(artifact) => {
                  setSelectedArtifact(artifact);
                  if (artifact.type === 'prd' || artifact.type === 'spec') {
                    setActiveTab('create');
                  } else if (artifact.type === 'issue') {
                    setActiveTab('issues');
                  }
                }} selectedPath={selectedArtifact?.path} />
              </div>
            </Accordion>

            <Accordion title="Properties" icon={Tag}>
              {selectedArtifact ? (
                <div className="space-y-3 p-1">
                  <div>
                    <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-widest mb-1">Name</div>
                    <div className="text-xs text-zinc-300 truncate">{selectedArtifact.name}</div>
                  </div>
                  <div>
                    <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-widest mb-1">Status</div>
                    <div className="text-xs text-zinc-300">
                      <span className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px]">
                        {selectedArtifact.status || 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] font-bold text-zinc-600 uppercase tracking-widest mb-1">Path</div>
                    <div className="text-[10px] text-zinc-500 font-mono break-all">{selectedArtifact.relPath}</div>
                  </div>
                </div>
              ) : (
                <div className="text-[10px] text-zinc-600 italic text-center py-4">No item selected</div>
              )}
            </Accordion>
          </div>

          <div className="p-4 border-t border-zinc-800 bg-zinc-900/30">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-1.5">
                <Coins size={12} className="text-amber-500/70" />
                Cost Tracking
              </div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700/30">
              <div className="text-lg font-bold text-zinc-100">${totalCost.toFixed(4)}</div>
              <div className="text-[9px] text-zinc-500 mt-0.5 uppercase font-medium">Estimated Usage</div>
            </div>
          </div>
        </Panel>

        <PanelResizeHandle className="w-1 bg-transparent hover:bg-blue-500/20 transition-colors" />

        {/* Center Pane: Main Content */}
        <Panel className="flex flex-col min-w-0">
          <div className="flex items-center gap-1 px-4 border-b border-zinc-800 bg-zinc-900/30">
            <TabButton 
              active={activeTab === 'planner'} 
              onClick={() => setActiveTab('planner')}
              icon={<Kanban size={14} />}
              label="Planner"
            />
            <TabButton 
              active={activeTab === 'create'} 
              onClick={() => setActiveTab('create')}
              icon={<PencilLine size={14} />}
              label="Create"
            />
            <TabButton 
              active={activeTab === 'issues'} 
              onClick={() => setActiveTab('issues')}
              icon={<Bug size={14} />}
              label="Issues"
            />
          </div>

          <main className="flex-1 overflow-y-auto relative p-6 no-scrollbar">
            {activeTab === 'planner' && (
              <div className="h-full flex flex-col gap-6 relative">
                <div className="flex items-center justify-between shrink-0">
                  <div>
                    <h2 className="text-2xl font-bold text-zinc-100">Project Planner</h2>
                    <p className="text-sm text-zinc-500 mt-1">Manage PRDs and track dependencies</p>
                  </div>
                  <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-1">
                    <button 
                      onClick={() => setPlannerView('board')}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all",
                        plannerView === 'board' ? "bg-zinc-800 text-blue-400 shadow-sm" : "text-zinc-500 hover:text-zinc-300"
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
                        plannerView === 'graph' ? "bg-zinc-800 text-blue-400 shadow-sm" : "text-zinc-500 hover:text-zinc-300"
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
                        setActiveTab('create');
                      }}
                      onRefresh={loadRegistry}
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
                            setActiveTab('create');
                         }
                      }}
                    />
                  )}
                </div>

                <div className="shrink-0 -mx-6 -mb-6 mt-4">
                  <AgentLogMonitor />
                </div>
              </div>
            )}
            {activeTab === 'create' && (
              selectedArtifact ? (
                <ArtifactContentView 
                  artifact={selectedArtifact} 
                  workspaceRoot={workspaceRoot} 
                />
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-zinc-500">
                  <div className="w-16 h-16 rounded-full bg-zinc-800/50 flex items-center justify-center mb-4">
                    <PencilLine size={32} className="text-zinc-600" />
                  </div>
                  <h3 className="text-lg font-medium text-zinc-300">Select a PRD to edit</h3>
                  <p className="text-sm mt-1">Browse PRDs from the Vibe Explorer sidebar</p>
                </div>
              )
            )}
            {activeTab === 'issues' && (
              <div className="h-full flex flex-col items-center justify-center text-zinc-600">
                <Bug size={48} className="mb-4 opacity-10" />
                <h3 className="text-lg font-medium text-zinc-400">Issue Management</h3>
                <p className="text-sm mt-1">Local and GitHub issues integration coming soon</p>
              </div>
            )}
          </main>
        </Panel>

        <PanelResizeHandle className="w-1 bg-transparent hover:bg-blue-500/20 transition-colors" />

        {/* Right Pane: AI / Interaction */}
        <Panel defaultSize={30} minSize={20} className="flex flex-col bg-zinc-900/20 border-l border-zinc-800">
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/30">
              <div className="flex items-center gap-2 font-semibold text-zinc-100">
                <MessageSquare size={16} className="text-blue-400" />
                <span className="text-xs uppercase tracking-widest font-bold">Agent Interaction</span>
              </div>
              <div className="flex gap-1">
                <button onClick={() => setMessages([])} className="p-1.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-red-400 transition-colors" title="Clear Chat">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-zinc-800">
              {messages.map((msg, i) => (
                <div key={i} className={cn(
                  "rounded-lg p-3 border",
                  msg.role === 'User' ? "bg-zinc-800/30 border-zinc-700/30 ml-4" : "bg-zinc-800/50 border-zinc-700/50 mr-4"
                )}>
                  <div className={cn(
                    "text-[10px] font-bold mb-1 uppercase tracking-wider",
                    msg.role === 'Architect' ? "text-blue-400" : msg.role === 'PM' ? "text-purple-400" : "text-emerald-400"
                  )}>
                    {msg.role}
                  </div>
                  <div className="text-sm prose prose-invert max-w-none text-zinc-300">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                </div>
              ))}
              
              {activeAgents.length > 0 && (
                <div className="pt-4 border-t border-zinc-800">
                  <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2 px-1">Active Processes</div>
                  <div className="space-y-2">
                    {activeAgents.map(agent => (
                      <div key={agent.pid} className="flex items-center justify-between bg-blue-500/5 border border-blue-500/20 rounded px-2 py-1.5">
                        <div className="flex items-center gap-2 overflow-hidden">
                          <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                          <span className="text-[10px] text-blue-300 font-mono truncate">{agent.command}</span>
                        </div>
                        <button 
                          onClick={() => handleCancelCommand(agent.pid)}
                          className="text-zinc-500 hover:text-red-400 p-0.5 rounded transition-colors"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-zinc-800 bg-zinc-900/50">
              {pendingPrompt && (
                <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <div className="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-1">Input Required</div>
                  <div className="text-xs text-zinc-200 mb-2">{pendingPrompt}</div>
                </div>
              )}
              
              {serverStatus && (
                <div className="mb-4 p-3 bg-zinc-800/50 border border-zinc-700 rounded-lg">
                  <div className="flex justify-between items-center mb-1.5">
                    <div className="text-[9px] font-bold text-zinc-500 uppercase tracking-widest">{serverStatus.phase}</div>
                    <div className="text-[9px] font-mono text-zinc-400">{serverStatus.progress}%</div>
                  </div>
                  <div className="w-full bg-zinc-950 rounded-full h-1 overflow-hidden">
                    <div 
                      className="bg-blue-500 h-full transition-all duration-500" 
                      style={{ width: `${serverStatus.progress}%` }} 
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
                  className="flex-1 bg-zinc-800 border border-zinc-700 rounded-md py-2 px-3 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 text-zinc-100"
                />
                <button 
                  onClick={handleSendMessage}
                  className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors shadow-lg shadow-blue-500/10"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </div>

          <div className="h-48 border-t border-zinc-800 bg-zinc-950 p-2 overflow-hidden flex flex-col">
            <div className="flex items-center gap-2 px-2 py-1 text-[9px] font-bold text-zinc-500 uppercase tracking-widest mb-1">
              <Terminal size={10} />
              Command Output
            </div>
            <div className="flex-1 overflow-y-auto font-mono text-[10px] p-2 bg-black/30 rounded scrollbar-none">
              <TerminalOutputView />
            </div>
          </div>
        </Panel>
      </PanelGroup>
    </div>
  );
};

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}

const TabButton: React.FC<TabButtonProps> = ({ active, onClick, icon, label }) => (
  <button 
    onClick={onClick}
    className={cn(
      "flex items-center gap-2 px-4 py-3 transition-all text-[10px] font-bold uppercase tracking-widest border-b-2",
      active 
        ? "border-blue-500 text-zinc-100 bg-blue-500/5" 
        : "border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30"
    )}
  >
    {icon}
    <span>{label}</span>
  </button>
);

export default App;

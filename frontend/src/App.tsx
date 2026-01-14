import React, { useState, useEffect, useRef, useMemo } from 'react';
import Ansi from 'ansi-to-react';
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
  Eye
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

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'ui-sans-serif, system-ui, sans-serif',
});

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type Tab = 'vibe' | 'explorer' | 'monitor' | 'runner' | 'testing';

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

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('vibe');
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [workspaceRoot, setWorkspaceRoot] = useState<string>('');
  const [activeAgents, setActiveAgents] = useState<AgentProcess[]>([]);
  const [totalCost, setTotalCost] = useState<number>(0);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'Architect',
      content: "Hello! I am the Architect agent. I've initialized the Vibe Explorer. You can now browse PRDs, System Specs, and Issues in a structured environment."
    }
  ]);
  const [inputValue, setInputValue] = useState('');

  useEffect(() => {
    invoke<string>('get_workspace_root')
      .then(setWorkspaceRoot)
      .catch(console.error);
    
    const interval = setInterval(() => {
      invoke<AgentProcess[]>('get_active_agents')
        .then(setActiveAgents)
        .catch(console.error);
      
      invoke<number>('get_total_cost')
        .then(setTotalCost)
        .catch(console.error);
    }, 3000);
    
    return () => clearInterval(interval);
  }, []);

  const handleSendMessage = () => {
    if (!inputValue.trim()) return;
    
    const content = inputValue.trim();
    setMessages([...messages, { role: 'User', content }]);
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
      setActiveTab('monitor');
    }
  };

  return (
    <div className="flex h-screen w-full bg-zinc-950 text-zinc-300 overflow-hidden font-sans">
      {/* Left Pane: Agent Chat Interface */}
      <div 
        className={cn(
          "flex flex-col border-r border-zinc-800 transition-all duration-300 ease-in-out bg-zinc-900/50",
          leftSidebarOpen ? "w-[400px]" : "w-0 overflow-hidden border-none"
        )}
      >
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-zinc-100">
            <MessageSquare size={18} className="text-blue-400" />
            <span>Agent Chat</span>
          </div>
          <button onClick={() => setLeftSidebarOpen(false)} className="hover:text-zinc-100">
            <ChevronLeft size={18} />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-zinc-800">
          {messages.map((msg, i) => (
            <div key={i} className={cn(
              "rounded-lg p-3 border",
              msg.role === 'User' ? "bg-zinc-800/30 border-zinc-700/30 ml-4" : "bg-zinc-800/50 border-zinc-700/50 mr-4"
            )}>
              <div className={cn(
                "text-xs font-bold mb-1 uppercase tracking-wider",
                msg.role === 'Architect' ? "text-blue-400" : msg.role === 'PM' ? "text-purple-400" : "text-emerald-400"
              )}>
                {msg.role}
              </div>
              <div className="text-sm prose prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                  {msg.content}
                </ReactMarkdown>
              </div>
            </div>
          ))}
          
          {activeAgents.length > 0 && (
            <div className="pt-4 border-t border-zinc-800">
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2">Active Agents</div>
              <div className="space-y-2">
                {activeAgents.map(agent => (
                  <div key={agent.pid} className="flex items-center justify-between bg-blue-500/10 border border-blue-500/20 rounded px-2 py-1.5">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                      <span className="text-[10px] text-blue-300 font-mono truncate">{agent.command}</span>
                    </div>
                    <span className="text-[10px] text-zinc-500 font-mono">PID:{agent.pid}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-zinc-800 bg-zinc-900">
          <div className="mb-3 flex flex-wrap gap-2">
            {['/status', '/prd list', '/issue list', '/test'].map(cmd => (
              <button 
                key={cmd}
                onClick={() => setInputValue(cmd)}
                className="text-[10px] bg-zinc-800 hover:bg-zinc-700 text-zinc-400 px-2 py-1 rounded transition-colors border border-zinc-700"
              >
                {cmd}
              </button>
            ))}
          </div>
          <div className="relative flex gap-2">
            <input 
              type="text" 
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Type a message..."
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-md py-2 px-3 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 text-zinc-100"
            />
            <button 
              onClick={handleSendMessage}
              className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Area: Dynamic Workspaces */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-zinc-800 flex items-center justify-between px-4 bg-zinc-900/80 backdrop-blur-sm sticky top-0 z-20">
          <div className="flex items-center gap-4 overflow-hidden">
            {!leftSidebarOpen && (
              <button 
                onClick={() => setLeftSidebarOpen(true)}
                className="p-2 hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-zinc-100 transition-all border border-zinc-800"
                title="Expand Chat"
              >
                <ChevronRight size={18} />
              </button>
            )}
            <div className="flex items-center gap-6 overflow-x-auto no-scrollbar">
               <TabButton 
                active={activeTab === 'vibe'} 
                onClick={() => setActiveTab('vibe')}
                icon={<LayoutDashboard size={16} />}
                label="Vibe Explorer"
              />
              <TabButton 
                active={activeTab === 'explorer'} 
                onClick={() => setActiveTab('explorer')}
                icon={<Files size={16} />}
                label="File Explorer"
              />
              <TabButton 
                active={activeTab === 'monitor'} 
                onClick={() => setActiveTab('monitor')}
                icon={<Activity size={16} />}
                label="Monitor"
              />
              <TabButton 
                active={activeTab === 'runner'} 
                onClick={() => setActiveTab('runner')}
                icon={<PlayCircle size={16} />}
                label="Runner"
              />
              <TabButton 
                active={activeTab === 'testing'} 
                onClick={() => setActiveTab('testing')}
                icon={<TestTube size={16} />}
                label="Testing"
              />
            </div>
          </div>
          {!rightSidebarOpen && (
            <button 
              onClick={() => setRightSidebarOpen(true)}
              className="p-2 hover:bg-zinc-800 rounded-md text-zinc-400 hover:text-zinc-100 transition-all border border-zinc-800"
              title="Expand Meta Info"
            >
              <ChevronLeft size={18} />
            </button>
          )}
        </header>

        <main className="flex-1 overflow-hidden relative">
          <div className="absolute inset-0 p-6 overflow-y-auto">
            {activeTab === 'vibe' && <VibeView root={workspaceRoot} />}
            {activeTab === 'explorer' && <ExplorerView root={workspaceRoot} />}
            {activeTab === 'monitor' && <MonitorView root={workspaceRoot} />}
            {activeTab === 'runner' && <RunnerView onRun={(cmd) => {
              setActiveTab('monitor');
            }} />}
            {activeTab === 'testing' && <TestingView />}
          </div>
        </main>
      </div>

      {/* Right Sidebar: Meta-Information */}
      <div 
        className={cn(
          "flex flex-col border-l border-zinc-800 transition-all duration-300 ease-in-out bg-zinc-900/50",
          rightSidebarOpen ? "w-72" : "w-0 overflow-hidden border-none"
        )}
      >
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold text-zinc-100">
            <Activity size={18} className="text-purple-400" />
            <span>Project Pulse</span>
          </div>
          <button onClick={() => setRightSidebarOpen(false)} className="hover:text-zinc-100">
            <ChevronRight size={18} />
          </button>
        </div>

        <div className="p-4 space-y-6 overflow-y-auto">
          <section>
            <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Project Status</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-400">Branch</span>
                <span className="text-zinc-200 font-mono text-xs truncate ml-2">feature/prd-38</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-400">Environment</span>
                <span className="text-green-500 font-medium">Development</span>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Active Services</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-zinc-300">Tauri Backend</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-zinc-300">File Watcher</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-zinc-300">Log Streamer</span>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-3">Cost Tracking</h3>
            <div className="bg-zinc-800/30 rounded p-3 border border-zinc-800">
              <div className="text-2xl font-bold text-zinc-100">${totalCost.toFixed(4)}</div>
              <div className="text-[10px] text-zinc-500 mt-1">Total project estimated usage</div>
            </div>
          </section>
        </div>
      </div>
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
      "flex items-center gap-2 px-3 py-1.5 rounded-md transition-all text-sm font-medium whitespace-nowrap",
      active 
        ? "bg-zinc-800 text-zinc-100" 
        : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
    )}
  >
    {icon}
    <span>{label}</span>
  </button>
);

const ExplorerView = ({ root }: { root: string }) => {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [currentPath, setCurrentPath] = useState(root);
  const [loading, setLoading] = useState(false);

  const refreshFiles = () => {
    if (currentPath) {
      setLoading(true);
      invoke<FileEntry[]>('list_directory', { path: currentPath })
        .then(setFiles)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  };

  useEffect(() => {
    if (root && !currentPath) {
      setCurrentPath(root);
    }
  }, [root]);

  useEffect(() => {
    refreshFiles();
  }, [currentPath]);

  useEffect(() => {
    const unlisten = listen('file-changed', (event: any) => {
      const changedPath = event.payload.path;
      if (changedPath.startsWith(currentPath)) {
        refreshFiles();
      }
    });
    return () => { unlisten.then(f => f()); };
  }, [currentPath]);

  const navigateUp = () => {
    const parts = currentPath.split(/[/\\]/);
    if (parts.length > 1) {
      if (parts[parts.length - 1] === '') parts.pop();
      parts.pop();
      const newPath = parts.join('/') || '/';
      setCurrentPath(newPath);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-zinc-100">File Explorer</h2>
        <div className="text-xs text-zinc-500 font-mono truncate max-w-md">
          {currentPath}
        </div>
      </div>
      
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <div className="p-2 border-b border-zinc-800 bg-zinc-800/30 flex items-center justify-between">
          <button 
            onClick={navigateUp}
            disabled={currentPath === root}
            className="px-2 py-1 text-xs bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300 transition-colors disabled:opacity-50"
          >
            .. / Up
          </button>
          <span className="text-[10px] text-zinc-500 uppercase font-bold tracking-widest px-2">
            {files.length} Items
          </span>
        </div>
        
        <div className="divide-y divide-zinc-800/50">
          {loading && files.length === 0 ? (
            <div className="p-8 text-center text-zinc-500 animate-pulse">Loading files...</div>
          ) : (
            files.map((file) => (
              <div 
                key={file.path} 
                className="flex items-center gap-3 p-3 hover:bg-zinc-800/50 transition-colors cursor-pointer group"
                onClick={() => file.is_dir && setCurrentPath(file.path)}
              >
                {file.is_dir ? (
                  <Folder size={18} className="text-blue-400 group-hover:text-blue-300" />
                ) : (
                  <FileText size={18} className="text-zinc-500 group-hover:text-zinc-400" />
                )}
                <span className={cn(
                  "text-sm transition-colors",
                  file.is_dir ? "text-zinc-200 font-medium" : "text-zinc-400"
                )}>
                  {file.name}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

interface LogEntry {
  id: string;
  timestamp?: string;
  level: 'INFO' | 'DEBUG' | 'ERROR' | 'NONE';
  message: string;
  details?: string[];
}

const LogLineComponent = ({ entry }: { entry: LogEntry }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasDetails = entry.details && entry.details.length > 0;

  const levelColors = {
    INFO: 'text-blue-400',
    DEBUG: 'text-zinc-500',
    ERROR: 'text-red-400',
    NONE: 'text-zinc-300'
  };

  return (
    <div className={cn(
      "group border-l-2 py-0.5 pl-2 transition-colors",
      entry.level === 'ERROR' ? "border-red-900/50 bg-red-900/10" : 
      entry.level === 'INFO' ? "border-blue-900/50" : "border-transparent hover:border-zinc-800"
    )}>
      <div className="flex items-start gap-2">
        {hasDetails && (
          <button 
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-1 p-0.5 hover:bg-zinc-800 rounded transition-colors"
          >
            {isExpanded ? <ChevronRight size={12} className="rotate-90" /> : <ChevronRight size={12} />}
          </button>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            {entry.level !== 'NONE' && (
              <span className={cn("text-[10px] font-bold px-1 rounded bg-zinc-800", levelColors[entry.level])}>
                {entry.level}
              </span>
            )}
            {entry.timestamp && <span className="text-[10px] text-zinc-600 font-mono">{entry.timestamp}</span>}
          </div>
          <div className={cn("whitespace-pre-wrap break-all", hasDetails ? "cursor-pointer" : "")} onClick={() => hasDetails && setIsExpanded(!isExpanded)}>
            <Ansi>{entry.message}</Ansi>
          </div>
          {isExpanded && hasDetails && (
            <div className="mt-2 pl-4 border-l border-zinc-800 space-y-0.5">
              {entry.details!.map((detail, idx) => (
                <div key={idx} className="text-zinc-500 text-[11px] whitespace-pre-wrap break-all">
                  <Ansi>{detail}</Ansi>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const MonitorView = ({ root }: { root: string }) => {
  const [logFiles, setLogFiles] = useState<FileEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [terminalOutput, setTerminalOutput] = useState<string[]>([]);
  const [filter, setFilter] = useState('');
  const [terminalFilter, setTerminalFilter] = useState('');
  const [logLevelFilter, setLogLevelFilter] = useState<'ALL' | 'INFO' | 'DEBUG' | 'ERROR'>('ALL');
  const scrollRef = useRef<HTMLDivElement>(null);
  const terminalScrollRef = useRef<HTMLDivElement>(null);
  const [followTail, setFollowTail] = useState(true);

  const groupLogs = (lines: string[]): LogEntry[] => {
    const entries: LogEntry[] = [];
    let currentEntry: LogEntry | null = null;

    for (const line of lines) {
      if (!line.trim()) continue;

      // Simple regex for log levels
      const levelMatch = line.match(/\[(INFO|DEBUG|ERROR)\]/);
      const isStackOrJson = line.startsWith('  ') || line.startsWith('\t') || line.startsWith('{') || line.startsWith('}') || line.startsWith('"') || line.startsWith('at ');

      if (levelMatch && !isStackOrJson) {
        if (currentEntry) entries.push(currentEntry);
        currentEntry = {
          id: Math.random().toString(36),
          level: levelMatch[1] as any,
          message: line,
          details: []
        };
      } else if (currentEntry && (isStackOrJson || !line.includes('['))) {
        currentEntry.details!.push(line);
      } else {
        if (currentEntry) entries.push(currentEntry);
        currentEntry = {
          id: Math.random().toString(36),
          level: 'NONE',
          message: line,
          details: []
        };
      }
    }
    if (currentEntry) entries.push(currentEntry);
    return entries;
  };

  const loadLogFiles = async () => {
    try {
      const files = await invoke<FileEntry[]>('list_logs', { root });
      setLogFiles(files);
      if (files.length > 0 && !selectedFile) {
        setSelectedFile(files[0].path);
      }
    } catch (e) {
      console.error('Error loading log files:', e);
    }
  };

  useEffect(() => {
    if (root) {
      loadLogFiles();
      // Load initial terminal buffer
      invoke<string[]>('get_terminal_buffer', { session: 'main' })
        .then(setTerminalOutput)
        .catch(console.error);
    }
  }, [root]);

  useEffect(() => {
    const unlisten = listen('log-file-changed', () => {
      loadLogFiles();
    });
    return () => { unlisten.then(f => f()); };
  }, []);

  useEffect(() => {
    if (selectedFile) {
      // Clear logs when switching files
      setLogs([]);
      // Start tailing
      invoke('tail_log_file', { path: selectedFile }).catch(console.error);
      // Also load initial content
      invoke<string>('read_file_content', { path: selectedFile })
        .then(content => {
          setLogs(content.split('\n').filter(l => l.length > 0));
        })
        .catch(console.error);
    }
  }, [selectedFile]);

  useEffect(() => {
    const unlistenNewLog = listen('new-log-line', (event: any) => {
      const payload = event.payload as { file: string, content: string };
      if (selectedFile?.endsWith(payload.file)) {
        setLogs(prev => [...prev, ...payload.content.split('\n').filter(l => l.length > 0)].slice(-5000));
      }
    });

    const unlistenTerminal = listen('log-line', (event: any) => {
      setTerminalOutput(prev => [...prev, event.payload as string].slice(-5000));
    });

    return () => { 
      unlistenNewLog.then(f => f()); 
      unlistenTerminal.then(f => f());
    };
  }, [selectedFile]);

  useEffect(() => {
    if (followTail && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, followTail]);

  useEffect(() => {
    if (followTail && terminalScrollRef.current) {
      terminalScrollRef.current.scrollTop = terminalScrollRef.current.scrollHeight;
    }
  }, [terminalOutput, followTail]);

  const filteredLogs = useMemo(() => {
    const grouped = groupLogs(logs);
    return grouped.filter(entry => {
      const matchesSearch = entry.message.toLowerCase().includes(filter.toLowerCase()) || 
                           entry.details?.some(d => d.toLowerCase().includes(filter.toLowerCase()));
      const matchesLevel = logLevelFilter === 'ALL' || entry.level === logLevelFilter;
      return matchesSearch && matchesLevel;
    });
  }, [logs, filter, logLevelFilter]);

  const filteredTerminalOutput = useMemo(() => {
    return terminalOutput.filter(line => 
      line.toLowerCase().includes(terminalFilter.toLowerCase())
    );
  }, [terminalOutput, terminalFilter]);

  return (
    <div className="h-full flex gap-4 overflow-hidden">
      {/* Session/File Sidebar */}
      <div className="w-64 flex flex-col gap-4 bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 overflow-hidden">
        <div className="flex items-center justify-between">
          <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Log Sessions</h3>
          <button onClick={loadLogFiles} className="text-zinc-500 hover:text-zinc-300">
            <RefreshCw size={12} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 pr-2">
          {logFiles.map(file => (
            <button
              key={file.path}
              onClick={() => setSelectedFile(file.path)}
              className={cn(
                "w-full text-left px-2 py-2 rounded text-[11px] transition-colors truncate flex items-center gap-2",
                selectedFile === file.path 
                  ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" 
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
              )}
            >
              <FileText size={14} className={cn(selectedFile === file.path ? "text-blue-400" : "text-zinc-600")} />
              <span className="truncate">{file.name}</span>
            </button>
          ))}
          {logFiles.length === 0 && (
            <div className="text-center py-8 text-zinc-600 text-xs">No logs found</div>
          )}
        </div>
      </div>

      {/* Main Content Areas */}
      <div className="flex-1 flex flex-col gap-4 overflow-hidden">
        {/* Log Viewer */}
        <div className="flex-[2] flex flex-col bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="p-3 border-b border-zinc-800 bg-zinc-900/50 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h2 className="text-sm font-bold text-zinc-200 flex items-center gap-2">
                <Activity size={16} className="text-blue-400" />
                Log Viewer
              </h2>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2 top-2 text-zinc-600" size={12} />
                  <input 
                    type="text" 
                    placeholder="Filter logs..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="bg-zinc-950 border border-zinc-800 rounded px-7 py-1 text-[11px] focus:outline-none focus:ring-1 focus:ring-blue-500 w-48"
                  />
                </div>
                <select
                  value={logLevelFilter}
                  onChange={(e) => setLogLevelFilter(e.target.value as any)}
                  className="bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-[11px] text-zinc-400 focus:outline-none"
                >
                  <option value="ALL">All Levels</option>
                  <option value="INFO">INFO</option>
                  <option value="DEBUG">DEBUG</option>
                  <option value="ERROR">ERROR</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setFollowTail(!followTail)}
                className={cn(
                  "px-2 py-1 rounded text-[10px] font-medium transition-colors border",
                  followTail ? "bg-blue-500/10 text-blue-400 border-blue-500/20" : "bg-zinc-900 text-zinc-500 border-zinc-800"
                )}
              >
                Follow Tail
              </button>
              <button onClick={() => setLogs([])} className="p-1 hover:bg-zinc-800 rounded text-zinc-500 hover:text-red-400 transition-colors">
                <Trash2 size={14} />
              </button>
            </div>
          </div>
          <div 
            ref={scrollRef}
            className="flex-1 bg-black/50 font-mono text-[12px] p-4 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800 space-y-0.5"
          >
            {filteredLogs.map((entry) => (
              <LogLineComponent key={entry.id} entry={entry} />
            ))}
            {filteredLogs.length === 0 && (
              <div className="h-full flex items-center justify-center text-zinc-600 italic">
                {logs.length === 0 ? "No log content yet..." : "No logs match your filter"}
              </div>
            )}
          </div>
        </div>

        {/* Terminal Output */}
        <div className="flex-1 flex flex-col bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
          <div className="px-3 py-2 border-b border-zinc-800 bg-zinc-900/80 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h2 className="text-[10px] font-bold text-zinc-400 flex items-center gap-2 uppercase tracking-widest">
                <Terminal size={12} />
                Terminal Output
              </h2>
              <div className="relative">
                <Search className="absolute left-2 top-1.5 text-zinc-600" size={10} />
                <input 
                  type="text" 
                  placeholder="Search terminal..."
                  value={terminalFilter}
                  onChange={(e) => setTerminalFilter(e.target.value)}
                  className="bg-zinc-950 border border-zinc-800 rounded px-6 py-0.5 text-[10px] focus:outline-none focus:ring-1 focus:ring-blue-500 w-32"
                />
              </div>
            </div>
            <button onClick={() => setTerminalOutput([])} className="text-zinc-600 hover:text-zinc-400">
              <Trash2 size={12} />
            </button>
          </div>
          <div 
            ref={terminalScrollRef}
            className="flex-1 font-mono text-[12px] p-4 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800 bg-black"
          >
            {filteredTerminalOutput.map((line, i) => (
              <div key={i} className="whitespace-pre-wrap break-all leading-relaxed">
                <Ansi>{line}</Ansi>
              </div>
            ))}
            {filteredTerminalOutput.length === 0 && (
              <div className="text-zinc-700 italic text-[11px]">
                {terminalOutput.length === 0 ? "Awaiting command output..." : "No matches found"}
              </div>
            )}
            <div className="inline-block w-1.5 h-3.5 bg-zinc-700 ml-1 animate-pulse translate-y-0.5" />
          </div>
        </div>
      </div>
    </div>
  );
};

const RunnerView = ({ onRun }: { onRun: (cmd: string) => void }) => {
  const commands = [
    { id: 'status', name: 'vibe status', description: 'Show project status' },
    { id: 'prd-list', name: 'vibe prd list', description: 'List all PRDs' },
    { id: 'issue-list', name: 'vibe issue list', description: 'List active issues' },
    { id: 'test', name: 'vibe testing run', description: 'Run project tests' },
    { id: 'cost', name: 'vibe cost', description: 'Show current cost' }
  ];

  const handleRun = (cmd: string) => {
    const [base, ...args] = cmd.split(' ');
    invoke('run_vibe_command', { command: args[0], args: args.slice(1) }).catch(console.error);
    onRun(cmd);
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-zinc-100">Runner</h2>
      <div className="space-y-4">
        {commands.map((cmd) => (
          <div key={cmd.id} className="flex items-center justify-between p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
            <div>
              <div className="font-mono text-blue-400 font-medium">{cmd.name}</div>
              <div className="text-xs text-zinc-500 mt-1">{cmd.description}</div>
            </div>
            <button 
              onClick={() => handleRun(cmd.name)}
              className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-950 rounded-md font-semibold text-sm hover:bg-white transition-colors"
            >
              <PlayCircle size={16} /> Run
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

const TestingView = () => (
  <div className="space-y-6">
    <h2 className="text-xl font-bold text-zinc-100">Testing</h2>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {[
        { name: 'Unit Tests', status: 'Passed', count: 42, time: '1.2s' },
        { name: 'Integration Tests', status: 'Failed', count: 12, time: '4.5s' },
        { name: 'E2E Tests', status: 'Pending', count: 5, time: '--' }
      ].map((test) => (
        <div key={test.name} className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="flex items-center justify-between mb-4">
            <span className="font-semibold text-zinc-200">{test.name}</span>
            <span className={cn(
              "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider",
              test.status === 'Passed' ? "bg-green-500/10 text-green-500" :
              test.status === 'Failed' ? "bg-red-500/10 text-red-500" : "bg-zinc-800 text-zinc-500"
            )}>
              {test.status}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <div className="flex items-center gap-1"><Database size={12} /><span>{test.count} tests</span></div>
            <div className="flex items-center gap-1"><Activity size={12} /><span>{test.time}</span></div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default App;

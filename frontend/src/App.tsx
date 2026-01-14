import React, { useState, useEffect, useRef, useMemo } from 'react';
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
  Split
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
}

// --- Components ---

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
  const timelineItems: { date: string, text: string, type: 'investigation' | 'solution' }[] = [];
  
  let currentType: 'investigation' | 'solution' | null = null;
  for (const line of lines) {
    if (line.includes('## Investigation Notes')) currentType = 'investigation';
    else if (line.includes('## Solution Notes')) currentType = 'solution';
    else if (currentType && line.trim().startsWith('- [')) {
      const match = line.match(/- \[(.*?)\] (.*)/);
      if (match) {
        timelineItems.push({ date: match[1], text: match[2], type: currentType });
      }
    }
  }

  if (timelineItems.length === 0) return null;

  return (
    <div className="mt-8 pt-8 border-t border-zinc-800">
      <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-widest mb-4">Update Timeline</h3>
      <div className="space-y-4">
        {timelineItems.map((item, i) => (
          <div key={i} className="flex gap-4">
            <div className="w-32 flex-shrink-0 text-[10px] font-mono text-zinc-500 pt-1">{item.date}</div>
            <div className="flex-1">
              <div className={cn(
                "text-[10px] font-bold uppercase mb-1",
                item.type === 'investigation' ? "text-blue-400" : "text-emerald-400"
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

const VibeView = ({ root }: { root: string }) => {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [content, setContent] = useState('');
  const [yamlData, setYamlData] = useState<any>(null);
  const [markdownContent, setMarkdownContent] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showSpecSplit, setShowSpecSplit] = useState(false);

  useEffect(() => {
    if (root) {
      loadArtifacts();
    }
  }, [root]);

  const loadArtifacts = async () => {
    try {
      const all: Artifact[] = [];
      
      const scan = async (dir: string, type: 'prd' | 'spec' | 'issue') => {
        try {
          const entries = await invoke<FileEntry[]>('list_directory', { path: dir });
          for (const f of entries) {
            if (f.is_dir) {
              await scan(f.path, type);
            } else if (f.name.endsWith('.md') || f.name.endsWith('.yaml')) {
              let status = '';
              let owner = '';
              try {
                const raw = await invoke<string>('read_file_content', { path: f.path });
                if (f.name.endsWith('.md')) {
                  const match = raw.match(/^---\n([\s\S]*?)\n---\n/);
                  if (match) {
                    const parsed: any = yaml.load(match[1]);
                    status = parsed.status || '';
                    owner = parsed.owner || parsed.agent || '';
                  }
                } else if (f.name.endsWith('.yaml')) {
                  const parsed: any = yaml.load(raw);
                  status = parsed.status || '';
                  owner = parsed.owner || '';
                }
              } catch (e) {}
              all.push({ name: f.name, path: f.path, type, status, owner });
            }
          }
        } catch (e) {}
      };

      await Promise.all([
        scan(`${root}/product`, 'prd'),
        scan(`${root}/implementation`, 'spec'),
        scan(`${root}/issues`, 'issue')
      ]);

      setArtifacts(all);
    } catch (err) {
      console.error('Error loading artifacts:', err);
    }
  };

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
              // Try to find corresponding markdown in product/
              const baseName = selectedArtifact.name.replace('.yaml', '');
              // Look for PRD or matching MD
              const prdPath = `${root}/product/${baseName}.md`;
              try {
                const md = await invoke<string>('read_file_content', { path: prdPath });
                setMarkdownContent(md);
              } catch (e) {
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

  const filteredArtifacts = artifacts.filter(a => 
    a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.status?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    a.owner?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-full gap-6 overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 flex flex-col gap-4 overflow-hidden">
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

        <div className="flex-1 overflow-y-auto space-y-1 pr-2">
          {['prd', 'spec', 'issue'].map(type => (
            <div key={type} className="mb-4">
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2 px-2">
                {type}s
              </div>
              {filteredArtifacts.filter(a => a.type === type).map(artifact => (
                <button
                  key={artifact.path}
                  onClick={() => setSelectedArtifact(artifact)}
                  className={cn(
                    "w-full text-left px-2 py-1.5 rounded text-xs transition-colors truncate",
                    selectedArtifact?.path === artifact.path 
                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" 
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                  )}
                >
                  {artifact.name}
                </button>
              ))}
            </div>
          ))}
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
                  <span className="text-zinc-500 text-xs font-mono">{selectedArtifact.path.replace(root, '')}</span>
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
                <button className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-xs font-medium text-zinc-200 transition-colors">
                  Open in Cursor
                </button>
              </div>
            </div>

            <FrontmatterCard data={yamlData} />

            {selectedArtifact.type === 'issue' && (
              <div className="mb-6 flex gap-2">
                <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest self-center mr-2">Quick Actions:</div>
                <button className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-[10px] font-medium text-zinc-300">Move to History</button>
                <button className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-[10px] font-medium text-zinc-300">Assign Agent</button>
                <button className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-[10px] font-medium text-zinc-300">Link PRD</button>
              </div>
            )}

            {selectedArtifact.type === 'spec' && showSpecSplit ? (
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-black/50 border border-zinc-800 rounded-lg p-4 font-mono text-xs overflow-x-auto">
                  <pre>{content}</pre>
                </div>
                <div className="prose prose-invert max-w-none">
                  <MarkdownRenderer content={markdownContent || "*No documentation found in product/*"} />
                </div>
              </div>
            ) : (
              <div className="prose prose-invert max-w-none">
                {selectedArtifact.type === 'spec' ? (
                   <div className="bg-black/50 border border-zinc-800 rounded-lg p-4 font-mono text-xs overflow-x-auto">
                    <pre>{content}</pre>
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
            {activeTab === 'monitor' && <MonitorView />}
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

const MonitorView = () => {
  const [logs, setLogs] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unlisten = listen('log-line', (event: any) => {
      setLogs(prev => [...prev, event.payload].slice(-10000));
    });
    return () => { unlisten.then(f => f()); };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="h-full flex flex-col space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-zinc-100">Monitor</h2>
        <button onClick={() => setLogs([])} className="px-2 py-1 bg-zinc-800 rounded text-xs hover:bg-zinc-700">Clear</button>
      </div>
      <div 
        ref={scrollRef}
        className="flex-1 bg-black border border-zinc-800 rounded-lg font-mono text-sm p-4 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800"
      >
        {logs.map((log, i) => (
          <div key={i} className={cn(log.startsWith('ERR:') ? "text-red-400" : "text-zinc-300")}>{log}</div>
        ))}
        <div className="animate-pulse inline-block w-2 h-4 bg-zinc-700 ml-1 translate-y-1" />
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

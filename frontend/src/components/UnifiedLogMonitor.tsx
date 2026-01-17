import React, { useState, useEffect, useRef, useMemo } from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/tauri';
import { 
  Terminal, 
  Maximize2, 
  Minimize2, 
  Activity, 
  ChevronUp, 
  ChevronDown,
  X,
  Server,
  Search,
  Trash2,
  Copy,
  Check,
  Filter,
  AlertCircle,
  Info,
  Bug,
  Cpu
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import Ansi from 'ansi-to-react';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface AppLog {
  id: string;
  timestamp: string;
  level: string;
  source: string;
  message: string;
  data?: any;
}

type LogTab = 'All' | 'System' | 'Commands' | 'Errors' | 'Agent';

const LogEntry = React.memo(({ 
  log, 
  isExpanded, 
  onToggle, 
  getLevelColor, 
  getSourceIcon 
}: { 
  log: AppLog, 
  isExpanded: boolean, 
  onToggle: () => void,
  getLevelColor: (l: string) => string,
  getSourceIcon: (s: string) => React.ReactNode
}) => {
  return (
    <div 
      className={cn(
        "flex flex-col group py-0.5 rounded px-1 transition-colors cursor-pointer",
        isExpanded 
          ? "bg-zinc-800/30 ring-1 ring-border/50 my-1" 
          : "hover:bg-zinc-800/20"
      )}
      onClick={onToggle}
    >
      <div className="flex gap-4 items-start">
        <span className="text-muted shrink-0 opacity-40 text-[10px] w-24 pt-0.5">{log.timestamp}</span>
        <span className={cn("shrink-0 font-bold text-[10px] w-16 pt-0.5", getLevelColor(log.level))}>
          {log.level}
        </span>
        <span className="shrink-0 flex items-center gap-1.5 text-muted/60 text-[10px] w-24 pt-0.5">
          {getSourceIcon(log.source)}
          {log.source}
        </span>
        <span className={cn("break-all flex-1", log.level === 'ERROR' ? "text-red-400" : "text-foreground opacity-90")}>
          <Ansi>{log.message}</Ansi>
        </span>
        <div className="shrink-0 text-muted/40 group-hover:text-muted/70 transition-colors">
          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>
      
      {isExpanded && (
        <div className="mt-2 ml-10 p-3 bg-black/40 rounded-lg border border-border/30 overflow-x-auto animate-in slide-in-from-top-1 duration-200">
          {log.data && typeof log.data === 'object' && ('command_line' in log.data || 'stdio' in log.data || 'stdout' in log.data || 'stderr' in log.data) ? (
            <div className="space-y-4">
              {log.data.command_line && (
                <div>
                  <div className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest mb-1 flex items-center gap-2">
                    <Terminal size={10} /> command line
                  </div>
                  <pre className="text-[10px] text-zinc-300 bg-black/40 p-2 rounded border border-white/10 whitespace-pre-wrap break-all font-mono leading-relaxed">
                    {typeof log.data.command_line === 'string' ? log.data.command_line : JSON.stringify(log.data.command_line, null, 2)}
                  </pre>
                </div>
              )}
              {log.data.stdio && (
                <div>
                  <div className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest mb-1 flex items-center gap-2">
                    <ChevronDown size={10} /> stdio (in)
                  </div>
                  <pre className="text-[10px] text-blue-300/90 bg-blue-950/20 p-2 rounded border border-blue-500/20 whitespace-pre-wrap break-all font-mono leading-relaxed">
                    {typeof log.data.stdio === 'string' ? log.data.stdio : JSON.stringify(log.data.stdio, null, 2)}
                  </pre>
                </div>
              )}
              {log.data.stdout && (
                <div>
                  <div className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest mb-1 flex items-center gap-2">
                    <ChevronUp size={10} /> stdout (out)
                  </div>
                  <pre className="text-[10px] text-emerald-300/90 bg-emerald-950/20 p-2 rounded border border-emerald-500/20 whitespace-pre-wrap break-all font-mono leading-relaxed">
                    {typeof log.data.stdout === 'string' ? log.data.stdout : JSON.stringify(log.data.stdout, null, 2)}
                  </pre>
                </div>
              )}
              {log.data.stderr && (
                <div>
                  <div className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest mb-1 flex items-center gap-2">
                    <AlertCircle size={10} /> stderr (error)
                  </div>
                  <pre className="text-[10px] text-red-300/90 bg-red-950/20 p-2 rounded border border-red-500/20 whitespace-pre-wrap break-all font-mono leading-relaxed">
                    {typeof log.data.stderr === 'string' ? log.data.stderr : JSON.stringify(log.data.stderr, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap break-all leading-relaxed font-mono bg-black/20 p-2 rounded border border-white/5">
              {log.data 
                ? (typeof log.data === 'string' ? log.data : JSON.stringify(log.data, null, 2))
                : `Timestamp: ${log.timestamp}\nLevel:     ${log.level}\nSource:    ${log.source}\nMessage:   ${log.message}`
              }
            </pre>
          )}
          <div className="flex justify-end mt-2 pt-2 border-t border-border/20">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                const detailText = log.data 
                  ? (typeof log.data === 'string' ? log.data : JSON.stringify(log.data, null, 2))
                  : `[${log.timestamp}] [${log.level}] [${log.source}] ${log.message}`;
                navigator.clipboard.writeText(detailText);
              }}
              className="text-[9px] font-bold text-muted-foreground hover:text-foreground transition-colors uppercase tracking-widest flex items-center gap-1.5"
            >
              <Copy size={10} />
              Copy Detail
            </button>
          </div>
        </div>
      )}
    </div>
  );
});

export const UnifiedLogMonitor = React.memo(({ accentColor, isDark = true }: { accentColor?: string, isDark?: boolean }) => {
  const [logs, setLogs] = useState<AppLog[]>([]);
  const [isExpanded, setIsExpanded] = useState(() => {
    return localStorage.getItem('vibe-logs-expanded') === 'true';
  });
  const [isFullView, setIsFullView] = useState(false);
  const [activeTab, setActiveTab] = useState<LogTab>(() => {
    return (localStorage.getItem('vibe-logs-tab') as LogTab) || 'All';
  });

  useEffect(() => {
    localStorage.setItem('vibe-logs-expanded', isExpanded.toString());
  }, [isExpanded]);

  useEffect(() => {
    localStorage.setItem('vibe-logs-tab', activeTab);
  }, [activeTab]);
  const [searchQuery, setSearchQuery] = useState('');
  const [copied, setCopied] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const logQueue = useRef<AppLog[]>([]);
  const flushTimer = useRef<any>(null);

  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 10;
      setAutoScroll(isAtBottom);
    }
  };

  useEffect(() => {
    setAutoScroll(true);
  }, [activeTab, searchQuery, isFullView, isExpanded]);

  const addLogsToState = (newLogs: AppLog[]) => {
    setLogs(prev => {
      const combined = [...prev, ...newLogs];
      return combined.slice(-500); // Limit total logs stored to 500
    });
  };

  useEffect(() => {
    // Initial load
    invoke<AppLog[]>('get_all_logs')
      .then(logs => {
        const logsWithId = logs.map(l => ({ ...l, id: l.id || `${Date.now()}-${Math.random()}` }));
        setLogs(logsWithId.slice(-500));
      })
      .catch(console.error);

    const flushLogs = () => {
      if (logQueue.current.length > 0) {
        const toAdd = [...logQueue.current];
        logQueue.current = [];
        addLogsToState(toAdd);
      }
      flushTimer.current = null;
    };

    const queueLog = (log: AppLog) => {
      logQueue.current.push(log);
      if (!flushTimer.current) {
        flushTimer.current = setTimeout(flushLogs, 100); // Batch logs every 100ms
      }
    };

    // Listen for new logs
    const unlistenAppLog = listen('app-log', (event: any) => {
      const log = { 
        ...(event.payload as AppLog), 
        id: `${Date.now()}-${Math.random()}` 
      };
      queueLog(log);
    });

    const unlistenCleared = listen('logs-cleared', () => {
      setLogs([]);
      logQueue.current = [];
    });

    // Support legacy Agent logs by converting them to AppLog
    const unlistenAgent = listen('vibe-server-event', (event: any) => {
      const payload = event.payload;
      let message = '';
      let level = 'INFO';
      let data = payload.data;
      
      if (payload.type === 'status') {
        message = `[${payload.phase}] ${payload.status} (${payload.progress}%)`;
      } else if (payload.type === 'log') {
        message = payload.message;
      } else if (payload.type === 'error') {
        message = payload.message;
        level = 'ERROR';
      } else if (payload.type === 'result') {
        message = `RESULT: ${payload.success ? 'Success' : 'Failed'}`;
        data = payload.result || payload;
      }

      if (message) {
        const log: AppLog = {
          id: `${Date.now()}-${Math.random()}`,
          timestamp: new Date().toLocaleTimeString(),
          level,
          source: 'Agent',
          message,
          data
        };
        queueLog(log);
      }
    });

    return () => {
      unlistenAppLog.then(f => f());
      unlistenCleared.then(f => f());
      unlistenAgent.then(f => f());
      if (flushTimer.current) clearTimeout(flushTimer.current);
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current && autoScroll) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isExpanded, isFullView, activeTab, searchQuery, autoScroll]);

  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const matchesTab = 
        activeTab === 'All' || 
        (activeTab === 'Errors' && log.level === 'ERROR') ||
        (activeTab === 'Commands' && log.source === 'Command') ||
        (activeTab === 'System' && log.source === 'System') ||
        (activeTab === 'Agent' && log.source === 'Agent');
      
      const matchesSearch = 
        log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.source.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.level.toLowerCase().includes(searchQuery.toLowerCase());

      return matchesTab && matchesSearch;
    });
  }, [logs, activeTab, searchQuery]);

  const handleClear = () => {
    invoke('clear_logs').catch(console.error);
  };

  const handleCopy = () => {
    const text = filteredLogs.map(l => `[${l.timestamp}] [${l.level}] [${l.source}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR': return 'text-red-400';
      case 'WARN': return 'text-amber-400';
      case 'DEBUG': return 'text-blue-400';
      default: return 'text-foreground opacity-90';
    }
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'Agent': return <Cpu size={12} className="text-purple-400" />;
      case 'Command': return <Terminal size={12} className="text-emerald-400" />;
      case 'System': return <Server size={12} className="text-blue-400" />;
      case 'FS': return <Info size={12} className="text-zinc-400" />;
      default: return <Activity size={12} className="text-zinc-400" />;
    }
  };

  if (isFullView) {
    return (
      <div className="fixed inset-0 z-50 bg-background flex flex-col p-6 animate-in fade-in duration-200">
        <div className="flex items-center justify-between mb-4 border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <Server style={{ color: accentColor }} size={20} />
            <h2 className="text-xl font-bold text-foreground">Application Logs</h2>
            <div className="flex bg-panel border border-border rounded-lg p-1 ml-4">
              {(['All', 'System', 'Commands', 'Agent', 'Errors'] as LogTab[]).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all",
                    activeTab === tab 
                      ? (isDark ? "bg-zinc-800 text-foreground shadow-sm" : "bg-zinc-200 text-foreground shadow-sm") 
                      : "text-muted hover:text-foreground"
                  )}
                  style={activeTab === tab ? { color: accentColor } : {}}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" size={14} />
              <input 
                type="text" 
                placeholder="Search logs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-panel border border-border rounded-md py-1.5 pl-9 pr-3 text-xs focus:outline-none focus:ring-1 focus:ring-accent w-64"
              />
            </div>
            <button 
              onClick={handleCopy}
              className="p-2 hover:bg-panel rounded-lg text-muted transition-colors flex items-center gap-2 text-xs"
              title="Copy to Clipboard"
            >
              {copied ? <Check size={16} className="text-green-500" /> : <Copy size={16} />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button 
              onClick={handleClear}
              className="p-2 hover:bg-panel rounded-lg text-muted hover:text-red-400 transition-colors flex items-center gap-2 text-xs"
              title="Clear Logs"
            >
              <Trash2 size={16} />
              Clear
            </button>
            <button 
              onClick={() => setIsFullView(false)}
              className="p-2 hover:bg-panel rounded-lg text-muted transition-colors"
            >
              <X size={20} />
            </button>
          </div>
        </div>
        
        <div 
          ref={scrollRef} 
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto font-mono text-xs space-y-0.5 p-4 bg-input rounded-xl border border-border/50 shadow-inner"
        >
          {filteredLogs.slice(-200).map((log) => (
            <LogEntry
              key={log.id}
              log={log}
              isExpanded={expandedId === log.id}
              onToggle={() => setExpandedId(expandedId === log.id ? null : log.id)}
              getLevelColor={getLevelColor}
              getSourceIcon={getSourceIcon}
            />
          ))}
          <div className="inline-block w-2 h-4 bg-muted ml-1 animate-pulse" />
        </div>
      </div>
    );
  }

  const lastLog = logs.length > 0 ? logs[logs.length - 1] : null;

  return (
    <div className={cn(
      "border-t border-border bg-background transition-all duration-300 flex flex-col relative z-30",
      isExpanded ? "h-64 shadow-2xl" : "h-12"
    )}>
      <div 
        className="h-12 px-4 flex items-center justify-between cursor-pointer hover:bg-panel transition-colors shrink-0"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 overflow-hidden flex-1">
          <div className={cn(
            "w-2 h-2 rounded-full",
            lastLog?.source === 'Agent' ? "bg-purple-500 animate-pulse" : "bg-muted"
          )} />
          <div className="flex items-center gap-2 text-[10px] font-bold text-muted uppercase tracking-widest whitespace-nowrap">
            <Activity size={12} style={{ color: lastLog?.source === 'Agent' ? accentColor : undefined }} />
            App Logs
          </div>
          {!isExpanded && lastLog && (
            <div className="text-[10px] text-muted truncate italic opacity-70 flex items-center gap-2">
              <span className="opacity-50">[{lastLog.timestamp}]</span>
              <span className={cn("font-bold", getLevelColor(lastLog.level))}>{lastLog.source}:</span>
              <span className="truncate max-w-2xl">{lastLog.message}</span>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={(e) => {
              e.stopPropagation();
              setIsFullView(true);
            }}
            className="p-1.5 hover:bg-panel rounded text-muted transition-colors"
          >
            <Maximize2 size={14} />
          </button>
          {isExpanded ? <ChevronDown size={14} className="text-muted" /> : <ChevronUp size={14} className="text-muted" />}
        </div>
      </div>

      {isExpanded && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center gap-4 px-4 py-1.5 border-b border-border bg-panel/30">
             {(['All', 'Agent', 'Commands', 'Errors'] as LogTab[]).map(tab => (
                <button
                  key={tab}
                  onClick={(e) => { e.stopPropagation(); setActiveTab(tab); }}
                  className={cn(
                    "px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider transition-all",
                    activeTab === tab 
                      ? (isDark ? "bg-zinc-800 text-foreground" : "bg-zinc-200 text-foreground") 
                      : "text-muted hover:text-foreground"
                  )}
                  style={activeTab === tab ? { color: accentColor } : {}}
                >
                  {tab}
                </button>
              ))}
              <div className="flex-1" />
              <button onClick={(e) => { e.stopPropagation(); handleClear(); }} className="text-muted hover:text-red-400 p-1">
                <Trash2 size={12} />
              </button>
          </div>
          <div 
            ref={scrollRef} 
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto px-4 pb-4 pt-2 font-mono text-[10px] space-y-0.5"
          >
            {filteredLogs.slice(-100).map((log) => (
              <LogEntry
                key={log.id}
                log={log}
                isExpanded={expandedId === log.id}
                onToggle={() => setExpandedId(expandedId === log.id ? null : log.id)}
                getLevelColor={getLevelColor}
                getSourceIcon={getSourceIcon}
              />
            ))}
            <div className="inline-block w-1.5 h-3 bg-muted ml-1 animate-pulse" />
          </div>
        </div>
      )}
    </div>
  );
});

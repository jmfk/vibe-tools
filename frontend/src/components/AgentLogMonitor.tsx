import React, { useState, useEffect, useRef } from 'react';
import { listen } from '@tauri-apps/api/event';
import { 
  Terminal, 
  Maximize2, 
  Minimize2, 
  Activity, 
  ChevronUp, 
  ChevronDown,
  X,
  Server
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import Ansi from 'ansi-to-react';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface LogEntry {
  timestamp: string;
  message: string;
  type?: string;
  level?: string;
}

export const AgentLogMonitor = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isFullView, setIsFullView] = useState(false);
  const [status, setStatus] = useState<'Working' | 'Idle'>('Idle');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unlisten = listen('vibe-server-event', (event: any) => {
      const payload = event.payload;
      
      let message = '';
      if (payload.type === 'status') {
        setStatus('Working');
        message = `[${payload.phase}] ${payload.status} (${payload.progress}%)`;
      } else if (payload.type === 'log') {
        message = payload.message;
      } else if (payload.type === 'error') {
        message = `ERROR: ${payload.message}`;
      } else if (payload.type === 'result') {
        setStatus('Idle');
        message = `RESULT: ${payload.success ? 'Success' : 'Failed'}`;
      }

      if (message) {
        setLogs(prev => [...prev, {
          timestamp: new Date().toLocaleTimeString(),
          message,
          type: payload.type
        }].slice(-500));
      }
    });

    const unlistenLog = listen('log-line', (event: any) => {
      const line = event.payload as string;
      // Also capture raw log lines that aren't JSON
      if (!line.startsWith('{')) {
        setLogs(prev => [...prev, {
          timestamp: new Date().toLocaleTimeString(),
          message: line,
          type: 'raw'
        }].slice(-500));
      }
    });

    return () => {
      unlisten.then(f => f());
      unlistenLog.then(f => f());
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isExpanded, isFullView]);

  const miniLogs = logs.slice(-5);

  if (isFullView) {
    return (
      <div className="fixed inset-0 z-50 bg-zinc-950 flex flex-col p-6">
        <div className="flex items-center justify-between mb-4 border-b border-zinc-800 pb-4">
          <div className="flex items-center gap-3">
            <Server className="text-blue-500" size={20} />
            <h2 className="text-xl font-bold text-zinc-100">Agent Server Logs</h2>
            <div className={cn(
              "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider",
              status === 'Working' ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-zinc-800 text-zinc-500"
            )}>
              {status}
            </div>
          </div>
          <button 
            onClick={() => setIsFullView(false)}
            className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-400 transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto font-mono text-sm space-y-1 p-4 bg-black/30 rounded-xl border border-zinc-800/50">
          {logs.map((log, i) => (
            <div key={i} className="flex gap-4">
              <span className="text-zinc-600 shrink-0">{log.timestamp}</span>
              <span className={cn(
                "break-all",
                log.type === 'error' ? "text-red-400" : 
                log.type === 'status' ? "text-blue-400" : "text-zinc-300"
              )}>
                <Ansi>{log.message}</Ansi>
              </span>
            </div>
          ))}
          <div className="inline-block w-2 h-4 bg-zinc-700 ml-1 animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "border-t border-zinc-800 bg-zinc-950 transition-all duration-300 flex flex-col",
      isExpanded ? "h-64" : "h-12"
    )}>
      <div 
        className="h-12 px-4 flex items-center justify-between cursor-pointer hover:bg-zinc-900/50 transition-colors shrink-0"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 overflow-hidden">
          <div className={cn(
            "w-2 h-2 rounded-full",
            status === 'Working' ? "bg-green-500 animate-pulse" : "bg-zinc-700"
          )} />
          <div className="flex items-center gap-2 text-[10px] font-bold text-zinc-500 uppercase tracking-widest whitespace-nowrap">
            <Activity size={12} />
            Agent Monitor: {status}
          </div>
          {!isExpanded && logs.length > 0 && (
            <div className="text-[10px] text-zinc-600 truncate italic">
              - {logs[logs.length - 1].message}
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={(e) => {
              e.stopPropagation();
              setIsFullView(true);
            }}
            className="p-1.5 hover:bg-zinc-800 rounded text-zinc-500 transition-colors"
          >
            <Maximize2 size={14} />
          </button>
          {isExpanded ? <ChevronDown size={14} className="text-zinc-500" /> : <ChevronUp size={14} className="text-zinc-500" />}
        </div>
      </div>

      {isExpanded && (
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 pb-4 font-mono text-[10px] space-y-0.5">
          {logs.slice(-50).map((log, i) => (
            <div key={i} className="flex gap-3">
              <span className="text-zinc-700 shrink-0">{log.timestamp}</span>
              <span className={cn(
                "truncate",
                log.type === 'error' ? "text-red-500/80" : 
                log.type === 'status' ? "text-blue-500/80" : "text-zinc-400"
              )}>
                <Ansi>{log.message}</Ansi>
              </span>
            </div>
          ))}
          <div className="inline-block w-1.5 h-3 bg-zinc-800 ml-1 animate-pulse" />
        </div>
      )}
    </div>
  );
};

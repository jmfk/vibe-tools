import React from 'react';
import { 
  MessageSquare, 
  Trash2, 
  Send 
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface Message {
  role: 'Architect' | 'PM' | 'User';
  content: string;
}

export interface AgentProcess {
  pid: number;
  command: string;
  chat_id: string | null;
  tracked: boolean;
}

interface AgentInteractionProps {
  messages: Message[];
  onClearChat: () => void;
  interactionMode: 'ASK' | 'AGENT';
  setInteractionMode: (mode: 'ASK' | 'AGENT') => void;
  accentColor: string;
  isDark: boolean;
  activeAgents: AgentProcess[];
  onCancelCommand: (pid?: number) => void;
  pendingPrompt: string | null;
  serverStatus: { phase: string, status: string, progress: number } | null;
  inputValue: string;
  setInputValue: (val: string) => void;
  onSendMessage: () => void;
}

export const AgentInteraction: React.FC<AgentInteractionProps> = ({
  messages,
  onClearChat,
  interactionMode,
  setInteractionMode,
  accentColor,
  isDark,
  activeAgents,
  onCancelCommand,
  pendingPrompt,
  serverStatus,
  inputValue,
  setInputValue,
  onSendMessage
}) => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="p-4 border-b flex items-center justify-between transition-colors duration-300 bg-panel border-border">
        <div className="flex items-center gap-2 font-semibold">
          <MessageSquare size={16} style={{ color: accentColor }} />
          <span className="text-xs uppercase tracking-widest font-bold">Agent Interaction</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-zinc-900/50 rounded-lg p-0.5 border border-border">
            {(['ASK', 'AGENT'] as const).map(m => (
              <button
                key={m}
                onClick={() => setInteractionMode(m)}
                className={cn(
                  "px-2 py-1 rounded-md text-[9px] font-bold transition-all",
                  interactionMode === m 
                    ? (isDark ? "bg-zinc-800 shadow-sm" : "bg-zinc-200 shadow-sm")
                    : "text-muted hover:text-foreground"
                )}
                style={interactionMode === m ? { color: accentColor } : {}}
              >
                {m}
              </button>
            ))}
          </div>
          <div className="w-px h-4 bg-border mx-1" />
          <button onClick={onClearChat} className="p-1.5 rounded transition-colors text-muted hover:text-red-400 hover:bg-zinc-800/20" title="Clear Chat">
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
            <div className={cn("text-sm prose max-w-none transition-colors duration-300", isDark ? "prose-invert" : "prose-zinc")}>
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
                    onClick={() => onCancelCommand(agent.pid)}
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
            onKeyDown={(e) => e.key === 'Enter' && onSendMessage()}
            placeholder="Ask the Architect..."
            className="flex-1 border rounded-md py-2 px-3 text-xs focus:outline-none focus:ring-2 transition-all duration-300 bg-input border-border focus:ring-accent/50"
          />
          <button 
            onClick={onSendMessage}
            className="p-2 text-white rounded-md transition-all shadow-lg active:scale-95"
            style={{ backgroundColor: accentColor }}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};

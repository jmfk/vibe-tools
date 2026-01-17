import React, { useState, useEffect } from 'react';
import { AlertCircle } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { listen } from '@tauri-apps/api/event';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ServerStatus {
  phase: string;
  status: string;
  progress: number;
}

export const StatusMonitor = React.memo(({ accentColor }: { accentColor: string }) => {
  const [serverStatus, setServerStatus] = useState<ServerStatus | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  useEffect(() => {
    const unlisten = listen('vibe-server-event', (event: any) => {
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
      }
    });

    return () => {
      unlisten.then(f => f());
    };
  }, []);

  if (!serverStatus && !pendingPrompt) return null;

  return (
    <div className="space-y-4 mb-4">
      {pendingPrompt && (
        <div className="p-3 bg-accent/10 border border-accent/30 rounded-lg shadow-sm">
          <div className="text-[10px] font-bold text-accent uppercase tracking-widest mb-1">Input Required</div>
          <div className="text-xs mb-2 font-medium">{pendingPrompt}</div>
        </div>
      )}
      
      {serverStatus && (
        <div className="p-3 border rounded-lg transition-colors duration-300 shadow-sm bg-background border-border">
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
    </div>
  );
});

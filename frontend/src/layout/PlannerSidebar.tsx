import React from 'react';
import { Files, Tag, Coins, RefreshCw, LayoutDashboard, FileText, X, AlertCircle } from 'lucide-react';
import { Accordion } from '../components/Accordion';
import { VibeSidebar, Artifact } from '../components/VibeSidebar';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface PlannerSidebarProps {
  workspaceRoot: string;
  selectedArtifact: Artifact | null;
  onSelectArtifact: (a: Artifact) => void;
  onEditArtifact: (a: Artifact) => void;
  accentColor: string;
  isDark: boolean;
  openArtifacts: Artifact[];
  onCloseArtifact: (path: string) => void;
}

export const PlannerSidebar: React.FC<PlannerSidebarProps> = ({
  workspaceRoot,
  selectedArtifact,
  onSelectArtifact,
  onEditArtifact,
  accentColor,
  isDark,
  openArtifacts,
  onCloseArtifact
}) => {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto no-scrollbar">
        <Accordion title="Open Documents" icon={Files} isDark={isDark}>
          <div className="flex-1 overflow-y-auto p-1 space-y-1 scrollbar-none">
            {openArtifacts.map((art) => (
              <div 
                key={art.path} 
                onClick={() => { 
                  onSelectArtifact(art); 
                  if (art.type === 'prd') onEditArtifact(art); 
                }} 
                className={cn(
                  "group flex items-center justify-between p-2 rounded-lg cursor-pointer transition-all", 
                  selectedArtifact?.path === art.path ? "bg-accent/10 border border-accent/20" : "hover:bg-panel border border-transparent"
                )}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText 
                    size={12} 
                    className={cn(
                      selectedArtifact?.path === art.path ? "text-accent" : "text-muted/60",
                      art.deleted && "text-red-500 opacity-100"
                    )} 
                    style={{ color: (selectedArtifact?.path === art.path && !art.deleted) ? accentColor : undefined }} 
                  />
                  <span className={cn(
                    "text-[11px] truncate", 
                    selectedArtifact?.path === art.path ? "text-foreground font-medium" : "text-muted",
                    art.deleted && "text-red-400/80 italic line-through"
                  )}>
                    {art.name}
                  </span>
                  {art.deleted && (
                    <AlertCircle size={10} className="text-red-500 shrink-0" title="File not found on disk" />
                  )}
                </div>
                <button 
                  onClick={(e) => { e.stopPropagation(); onCloseArtifact(art.path); }} 
                  className="p-1 rounded hover:bg-zinc-800 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X size={10} className="text-muted" />
                </button>
              </div>
            ))}
            {openArtifacts.length === 0 && (
              <div className="py-8 text-center">
                <Files size={24} className="mx-auto mb-2 opacity-10" />
                <p className="text-[10px] text-muted opacity-50 uppercase tracking-tighter">No open docs</p>
              </div>
            )}
          </div>
        </Accordion>

        <Accordion title="Properties" icon={Tag} isDark={isDark}>
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
    </div>
  );
};

import React from 'react';
import { Files, Tag, Coins, RefreshCw, LayoutDashboard } from 'lucide-react';
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
  totalCost: number;
  onFetchUsage: () => void;
}

export const PlannerSidebar: React.FC<PlannerSidebarProps> = ({
  workspaceRoot,
  selectedArtifact,
  onSelectArtifact,
  onEditArtifact,
  accentColor,
  isDark,
  totalCost,
  onFetchUsage
}) => {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto no-scrollbar">
        <Accordion title="Vibe Explorer (PRDs)" icon={Files} isDark={isDark}>
          <div className="mt-2">
            <VibeSidebar 
              root={workspaceRoot} 
              onSelect={onSelectArtifact} 
              onEdit={onEditArtifact}
              selectedPath={selectedArtifact?.path} 
              accentColor={accentColor} 
              isDark={isDark} 
            />
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

      <div 
        className="p-4 border-t transition-colors duration-300 bg-panel border-border cursor-pointer hover:bg-zinc-800/30 group/cost"
        onClick={onFetchUsage}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 text-muted group-hover/cost:text-foreground transition-colors">
            <Coins size={12} className="text-amber-500/70" />
            Cost Tracking
          </div>
          <RefreshCw size={10} className="text-muted opacity-0 group-hover/cost:opacity-100 transition-all" />
        </div>
        <div className="rounded-lg p-3 border shadow-inner transition-colors duration-300 bg-background border-border group-hover/cost:border-accent/30">
          <div className="text-lg font-bold">${totalCost.toFixed(4)}</div>
          <div className="text-[9px] mt-0.5 uppercase font-medium text-muted">Estimated Usage</div>
        </div>
      </div>
    </div>
  );
};

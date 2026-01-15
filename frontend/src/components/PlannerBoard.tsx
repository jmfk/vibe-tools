import React, { useState, useEffect, useMemo } from 'react';
import { 
  DndContext, 
  DragOverlay, 
  closestCorners, 
  KeyboardSensor, 
  PointerSensor, 
  useSensor, 
  useSensors,
  DragStartEvent,
  DragOverEvent,
  DragEndEvent,
  useDroppable
} from '@dnd-kit/core';
import { 
  arrayMove, 
  SortableContext, 
  sortableKeyboardCoordinates, 
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { invoke } from '@tauri-apps/api/tauri';
import { 
  MoreVertical, 
  Clock, 
  CheckCircle2, 
  PlayCircle, 
  User,
  GripVertical,
  Eye, 
  EyeOff,
  Plus,
  X,
  Check,
  Pencil,
  Save,
  ArrowLeft
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import yaml from 'js-yaml';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface PRD {
  id: string;
  title: string;
  path: string;
  status: string;
  owner?: string;
  depends_on?: string[];
  columnId: string;
  filename: string;
}

interface Column {
  id: string;
  title: string;
  folder: string;
  defaultVisible?: boolean;
}

const COLUMNS: Column[] = [
  { id: 'inbox', title: 'Inbox', folder: 'product/inbox', defaultVisible: true },
  { id: 'backlog', title: 'Backlog', folder: 'product/backlog', defaultVisible: true },
  { id: 'next', title: 'Next', folder: 'product/next', defaultVisible: true },
  { id: 'history', title: 'History', folder: 'product/history', defaultVisible: false },
];

const IN_PROGRESS_COLUMN: Column = { id: 'in_progress', title: 'In Progress', folder: 'product/in_progress' };

interface SortablePRDCardProps {
  prd: PRD;
  onClick?: (prd: PRD) => void;
}

const SortablePRDCard = ({ prd, onClick, accentColor }: SortablePRDCardProps & { accentColor?: string }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: prd.id, data: prd });

  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "bg-panel border border-border rounded-lg p-3 shadow-sm hover:border-zinc-700 transition-colors cursor-default group relative",
        isDragging && "z-50"
      )}
      onClick={() => onClick?.(prd)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] font-mono font-bold" style={{ color: accentColor }}>{prd.id}</span>
            {prd.owner && (
               <div className="flex items-center gap-1 px-1 py-0.5 rounded bg-panel border border-border text-[8px] text-muted">
                <User size={8} />
                {prd.owner}
               </div>
            )}
          </div>
          <h4 className="text-xs font-semibold text-foreground line-clamp-2 leading-snug">{prd.title}</h4>
        </div>
        <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing text-muted hover:text-foreground p-1 -mr-1">
          <GripVertical size={14} />
        </div>
      </div>
      
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {prd.columnId === 'in_progress' ? (
            <div className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider" style={{ color: accentColor }}>
              <div className="w-1 h-1 rounded-full animate-pulse" style={{ backgroundColor: accentColor }} />
              Implementing
            </div>
          ) : prd.columnId === 'history' ? (
            <div className="flex items-center gap-1 text-[9px] text-muted font-bold uppercase tracking-wider">
              <CheckCircle2 size={10} />
              Done
            </div>
          ) : (
            <div className="flex items-center gap-1 text-[9px] text-muted font-bold uppercase tracking-wider">
              <Clock size={10} />
              {prd.columnId}
            </div>
          )}
        </div>
        
        {prd.depends_on && prd.depends_on.length > 0 && (
          <div className="text-[9px] text-muted font-medium opacity-70">
            {prd.depends_on.length} dep{prd.depends_on.length > 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  );
};

export const PlannerBoard = ({ 
  workspaceRoot, 
  onSelectPRD,
  onRefresh,
  accentColor
}: { 
  workspaceRoot: string; 
  onSelectPRD: (prd: PRD) => void;
  onRefresh?: () => void;
  accentColor?: string;
}) => {
  const [prds, setPrds] = useState<PRD[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isAddingPRD, setIsAddingPRD] = useState(false);
  const [newPRDTitle, setNewPRDTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>({
    inbox: true,
    backlog: true,
    next: true,
    history: false
  });

  const sensors = useSensors(
    useSensor(PointerSensor, {
        activationConstraint: {
            distance: 5,
        },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const loadPRDs = async () => {
    if (!workspaceRoot) return;
    try {
      const allPRDs: PRD[] = [];
      const allCols = [...COLUMNS, IN_PROGRESS_COLUMN];
      for (const col of allCols) {
        const path = `${workspaceRoot}/${col.folder}`;
        try {
          const entries = await invoke<any[]>('list_directory', { path });
          for (const entry of entries) {
            if (!entry.is_dir && entry.name.endsWith('.md')) {
              const content = await invoke<string>('read_file_content', { path: entry.path });
              const match = content.match(/```yaml\n([\s\S]*?)\n```/);
              let meta: any = {};
              if (match) {
                try {
                  meta = yaml.load(match[1]);
                } catch (e) {}
              }
              
              allPRDs.push({
                id: meta.id || entry.name.replace('.md', ''),
                title: meta.title || entry.name,
                path: entry.path,
                status: meta.status || '',
                owner: meta.agent || meta.owner,
                depends_on: meta.depends_on,
                columnId: col.id,
                filename: entry.name
              });
            }
          }
        } catch (e) {}
      }
      setPrds(allPRDs);
      
      // Auto-show/hide inbox based on content
      const inboxItems = allPRDs.filter(p => p.columnId === 'inbox');
      if (inboxItems.length > 0 || isAddingPRD) {
        setVisibleColumns(prev => ({ ...prev, inbox: true }));
      } else {
        setVisibleColumns(prev => ({ ...prev, inbox: false }));
      }
    } catch (err) {
      console.error('Failed to load PRDs for board:', err);
    }
  };

  useEffect(() => {
    loadPRDs();
  }, [workspaceRoot]);

  const handleCreatePRD = async () => {
    if (!newPRDTitle.trim() || !workspaceRoot || isSubmitting) return;
    
    setIsSubmitting(true);
    try {
      // 1. Generate ID
      let maxId = 0;
      prds.forEach(p => {
        const match = p.id.match(/PRD-(\d+)/);
        if (match) {
          const num = parseInt(match[1]);
          if (num > maxId) maxId = num;
        }
      });
      const newId = `PRD-${(maxId + 1).toString().padStart(3, '0')}`;
      
      // 2. Sanitize filename
      const safeTitle = newPRDTitle.toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
      const filename = `${newId}-${safeTitle}.md`;
      const path = `${workspaceRoot}/product/inbox/${filename}`;
      
      // 3. Construct content
      const content = `# ${newPRDTitle}

## Overview
- **Problem statement**: 
- **User benefits**: 
- **Success criteria**: 

---
<details>
<summary>Metadata</summary>

\`\`\`yaml
id: ${newId}
title: ${newPRDTitle}
type: FEATURE
status: inbox
created_at: '${new Date().toISOString()}'
updated_at: '${new Date().toISOString()}'
\`\`\`
</details>

<!-- vibe-id: ${newId} -->
`;

      // 4. Write file
      await invoke('write_file_content', { path, content });
      
      // 5. Refresh and cleanup
      setNewPRDTitle('');
      setIsAddingPRD(false);
      setVisibleColumns(prev => ({ ...prev, inbox: true }));
      await loadPRDs();
      onRefresh?.();
    } catch (err) {
      console.error('Failed to create PRD:', err);
      alert('Failed to create PRD. Check console for details.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const activePRD = prds.find(p => p.id === activeId);
    if (!activePRD) return;

    const overColumn = [...COLUMNS, IN_PROGRESS_COLUMN].find(c => c.id === overId);
    const overPRD = prds.find(p => p.id === overId);

    const newColumnId = overColumn ? overColumn.id : overPRD?.columnId;

    if (newColumnId && activePRD.columnId !== newColumnId) {
      setPrds(prev => prev.map(p => 
        p.id === activeId ? { ...p, columnId: newColumnId } : p
      ));
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);

    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const activePRD = prds.find(p => p.id === activeId);
    if (!activePRD) return;

    const overColumn = [...COLUMNS, IN_PROGRESS_COLUMN].find(c => c.id === overId);
    const overPRD = prds.find(p => p.id === overId);
    const newColumnId = overColumn ? overColumn.id : overPRD?.columnId;

    if (!newColumnId) return;

    const oldColumnId = active.data.current?.columnId;
    
    if (newColumnId !== oldColumnId) {
      const targetColumn = [...COLUMNS, IN_PROGRESS_COLUMN].find(c => c.id === newColumnId)!;
      const newPath = `${workspaceRoot}/${targetColumn.folder}/${activePRD.filename}`;
      
      try {
        if (newColumnId === 'in_progress') {
          const alreadyInProgress = prds.find(p => p.columnId === 'in_progress' && p.id !== activeId);
          if (alreadyInProgress) {
            alert('Only one PRD can be In Progress at a time.');
            loadPRDs();
            return;
          }
          
          await invoke('move_file', { from: activePRD.path, to: newPath });
          await invoke('update_artifact_meta', { path: newPath, status: 'in_progress' });
          await invoke('run_vibe_command', { 
            command: 'implement', 
            args: [activePRD.id] 
          });
        } else if (oldColumnId === 'in_progress' && newColumnId === 'next') {
          await invoke('send_vibe_input', { input: JSON.stringify({ type: 'cancel' }) });
          await invoke('move_file', { from: activePRD.path, to: newPath });
          await invoke('update_artifact_meta', { path: newPath, status: 'next' });
        } else {
          await invoke('move_file', { from: activePRD.path, to: newPath });
          await invoke('update_artifact_meta', { path: newPath, status: newColumnId === 'history' ? 'completed' : newColumnId });
        }
        
        loadPRDs();
        onRefresh?.();
      } catch (err) {
        console.error('Failed to move PRD:', err);
        loadPRDs();
      }
    } else {
      const oldIndex = prds.findIndex(p => p.id === activeId);
      const newIndex = prds.findIndex(p => p.id === overId);
      if (oldIndex !== newIndex && newIndex !== -1) {
        setPrds(prev => arrayMove(prev, oldIndex, newIndex));
      }
    }
  };

  const activePRD = useMemo(() => prds.find(p => p.id === activeId), [prds, activeId]);
  const inProgressPRD = useMemo(() => prds.find(p => p.columnId === 'in_progress'), [prds]);

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-sm font-bold text-muted uppercase tracking-widest">Project Roadmap</h3>
          
          <button 
            onClick={() => {
              setIsAddingPRD(true);
              setVisibleColumns(prev => ({ ...prev, inbox: true }));
            }}
            className="px-2 py-1 bg-accent/10 hover:bg-accent/20 text-accent rounded text-[9px] font-bold uppercase tracking-wider transition-colors flex items-center gap-1.5 border border-accent/20"
            style={{ color: accentColor, borderColor: `${accentColor}30` }}
          >
            <Plus size={10} />
            New PRD
          </button>

          <div className="flex items-center gap-1 bg-panel/50 border border-border rounded-md px-1 py-0.5">
            {COLUMNS.map(col => (
              <button
                key={col.id}
                onClick={() => setVisibleColumns(prev => ({ ...prev, [col.id]: !prev[col.id] }))}
                className={cn(
                  "px-2 py-1 rounded text-[9px] font-bold uppercase tracking-wider transition-all flex items-center gap-1.5",
                  visibleColumns[col.id] 
                    ? "bg-zinc-800 text-foreground" 
                    : "text-muted hover:text-foreground/70"
                )}
              >
                {visibleColumns[col.id] ? <Eye size={10} /> : <EyeOff size={10} />}
                {col.title}
              </button>
            ))}
          </div>
        </div>
        
        <button 
          onClick={loadPRDs}
          className="p-1.5 hover:bg-zinc-800 rounded text-muted transition-colors"
        >
          <MoreVertical size={14} />
        </button>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="flex-1 flex flex-col gap-6 min-h-0">
          <div className="shrink-0">
            <div className="flex items-center gap-2 mb-3 px-1">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[10px] font-bold text-foreground uppercase tracking-widest">Active Implementation</span>
            </div>
            
            <div 
              className={cn(
                "h-24 rounded-xl border border-dashed flex items-center justify-center transition-all",
                inProgressPRD ? "bg-panel border-border border-solid p-4" : "bg-zinc-900/20 border-border/50"
              )}
            >
              <SortableContext
                id="in_progress"
                items={inProgressPRD ? [inProgressPRD.id] : []}
                strategy={verticalListSortingStrategy}
              >
                {inProgressPRD ? (
                  <div className="w-full max-w-2xl">
                    <SortablePRDCard prd={inProgressPRD} onClick={onSelectPRD} accentColor={accentColor} />
                  </div>
                ) : (
                  <div className="text-xs text-muted flex items-center gap-2 italic">
                    <PlayCircle size={14} />
                    Drag a PRD here to start implementation
                  </div>
                )}
              </SortableContext>
            </div>
          </div>

          <div className="flex-1 flex gap-4 min-h-0 overflow-x-auto pb-4 no-scrollbar">
            {COLUMNS.filter(col => visibleColumns[col.id]).map(column => (
              <div key={column.id} className="flex flex-col gap-3 min-w-[250px] max-w-[350px]">
                <div className="flex items-center justify-between px-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-muted uppercase tracking-widest opacity-80">{column.title}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-panel border border-border text-muted font-mono">
                      {prds.filter(p => p.columnId === column.id).length}
                    </span>
                  </div>
                </div>
                
                <div className="flex-1 bg-panel/30 rounded-xl border border-border/50 p-2 overflow-y-auto no-scrollbar">
                  <SortableContext
                    id={column.id}
                    items={prds.filter(p => p.columnId === column.id).map(p => p.id)}
                    strategy={verticalListSortingStrategy}
                  >
                    <div className="space-y-2 min-h-[150px]">
                      {column.id === 'inbox' && isAddingPRD && (
                        <div className="bg-panel border border-accent/30 rounded-lg p-3 shadow-sm animate-in fade-in slide-in-from-top-2 duration-200">
                          <input
                            autoFocus
                            type="text"
                            placeholder="PRD Title..."
                            value={newPRDTitle}
                            onChange={(e) => setNewPRDTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleCreatePRD();
                              if (e.key === 'Escape') {
                                setIsAddingPRD(false);
                                setNewPRDTitle('');
                              }
                            }}
                            className="w-full bg-transparent text-xs font-semibold text-foreground focus:outline-none mb-3"
                          />
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => {
                                setIsAddingPRD(false);
                                setNewPRDTitle('');
                              }}
                              className="p-1 hover:bg-zinc-800 rounded text-muted transition-colors"
                            >
                              <X size={14} />
                            </button>
                            <button
                              onClick={handleCreatePRD}
                              disabled={!newPRDTitle.trim() || isSubmitting}
                              className="p-1 bg-accent text-white rounded hover:bg-accent/80 transition-colors disabled:opacity-50"
                              style={{ backgroundColor: accentColor }}
                            >
                              {isSubmitting ? (
                                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                              ) : (
                                <Check size={14} />
                              )}
                            </button>
                          </div>
                        </div>
                      )}
                      {prds
                        .filter(p => p.columnId === column.id)
                        .map(prd => (
                          <SortablePRDCard key={prd.id} prd={prd} onClick={onSelectPRD} accentColor={accentColor} />
                        ))}
                    </div>
                  </SortableContext>
                </div>
              </div>
            ))}
          </div>
        </div>

        <DragOverlay>
          {activePRD ? <SortablePRDCard prd={activePRD} accentColor={accentColor} /> : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
};

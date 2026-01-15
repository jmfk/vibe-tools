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
  DefaultAnnouncements,
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
  FileText, 
  MoreVertical, 
  Clock, 
  CheckCircle2, 
  PlayCircle, 
  Inbox,
  ArrowRight,
  Archive,
  User,
  GripVertical
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
}

const COLUMNS: Column[] = [
  { id: 'inbox', title: 'Inbox', folder: 'product/inbox' },
  { id: 'backlog', title: 'Backlog', folder: 'product/backlog' },
  { id: 'next', title: 'Next', folder: 'product/next' },
  { id: 'in_progress', title: 'In Progress', folder: 'product/in_progress' },
  { id: 'archive', title: 'Archive', folder: 'product/history' },
];

interface SortablePRDCardProps {
  prd: PRD;
  onClick?: (prd: PRD) => void;
}

const SortablePRDCard = ({ prd, onClick }: SortablePRDCardProps) => {
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
        "bg-zinc-900 border border-zinc-800 rounded-lg p-3 shadow-sm hover:border-zinc-700 transition-colors cursor-default group relative",
        isDragging && "z-50"
      )}
      onClick={() => onClick?.(prd)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[10px] font-mono font-bold text-blue-500/80">{prd.id}</span>
            {prd.owner && (
               <div className="flex items-center gap-1 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[8px] text-zinc-400">
                <User size={8} />
                {prd.owner}
               </div>
            )}
          </div>
          <h4 className="text-xs font-semibold text-zinc-200 line-clamp-2 leading-snug">{prd.title}</h4>
        </div>
        <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing text-zinc-600 hover:text-zinc-400 p-1 -mr-1">
          <GripVertical size={14} />
        </div>
      </div>
      
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {prd.columnId === 'in_progress' ? (
            <div className="flex items-center gap-1 text-[9px] text-green-400 font-bold uppercase tracking-wider">
              <div className="w-1 h-1 rounded-full bg-green-400 animate-pulse" />
              Implementing
            </div>
          ) : prd.columnId === 'archive' ? (
            <div className="flex items-center gap-1 text-[9px] text-zinc-500 font-bold uppercase tracking-wider">
              <CheckCircle2 size={10} />
              Done
            </div>
          ) : (
            <div className="flex items-center gap-1 text-[9px] text-zinc-500 font-bold uppercase tracking-wider">
              <Clock size={10} />
              {prd.columnId}
            </div>
          )}
        </div>
        
        {prd.depends_on && prd.depends_on.length > 0 && (
          <div className="text-[9px] text-zinc-600 font-medium">
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
  onRefresh
}: { 
  workspaceRoot: string; 
  onSelectPRD: (prd: PRD) => void;
  onRefresh?: () => void;
}) => {
  const [prds, setPrds] = useState<PRD[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

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
      for (const col of COLUMNS) {
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
    } catch (err) {
      console.error('Failed to load PRDs for board:', err);
    }
  };

  useEffect(() => {
    loadPRDs();
  }, [workspaceRoot]);

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

    // Find if we are over a column or a card
    const overColumn = COLUMNS.find(c => c.id === overId);
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

    const overColumn = COLUMNS.find(c => c.id === overId);
    const overPRD = prds.find(p => p.id === overId);
    const newColumnId = overColumn ? overColumn.id : overPRD?.columnId;

    if (!newColumnId) return;

    const oldColumnId = active.data.current?.columnId;
    
    if (newColumnId !== oldColumnId) {
      const targetColumn = COLUMNS.find(c => c.id === newColumnId)!;
      const newPath = `${workspaceRoot}/${targetColumn.folder}/${activePRD.filename}`;
      
      try {
        // Handle logic & constraints
        if (newColumnId === 'in_progress') {
          // Check if another PRD is already in progress
          const alreadyInProgress = prds.find(p => p.columnId === 'in_progress' && p.id !== activeId);
          if (alreadyInProgress) {
            alert('Only one PRD can be In Progress at a time.');
            loadPRDs();
            return;
          }
          
          await invoke('move_file', { from: activePRD.path, to: newPath });
          await invoke('update_artifact_meta', { path: newPath, status: 'in_progress' });
          
          // Trigger vibe implement
          await invoke('run_vibe_command', { 
            command: 'implement', 
            args: [activePRD.id] 
          });
        } else if (oldColumnId === 'in_progress' && newColumnId === 'next') {
          // Cancel current implementation
          await invoke('send_vibe_input', { input: JSON.stringify({ type: 'cancel' }) });
          await invoke('move_file', { from: activePRD.path, to: newPath });
          await invoke('update_artifact_meta', { path: newPath, status: 'next' });
        } else {
          await invoke('move_file', { from: activePRD.path, to: newPath });
          await invoke('update_artifact_meta', { path: newPath, status: newColumnId === 'archive' ? 'completed' : newColumnId });
        }
        
        loadPRDs();
        onRefresh?.();
      } catch (err) {
        console.error('Failed to move PRD:', err);
        loadPRDs();
      }
    } else {
      // Reorder within column if needed (optional for now, dnd-kit handles local state)
      const oldIndex = prds.findIndex(p => p.id === activeId);
      const newIndex = prds.findIndex(p => p.id === overId);
      if (oldIndex !== newIndex) {
        setPrds(prev => arrayMove(prev, oldIndex, newIndex));
      }
    }
  };

  const activePRD = useMemo(() => prds.find(p => p.id === activeId), [prds, activeId]);

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-zinc-500 uppercase tracking-widest">Project Roadmap</h3>
        <button 
          onClick={loadPRDs}
          className="p-1.5 hover:bg-zinc-800 rounded text-zinc-500 transition-colors"
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
        <div className="flex-1 grid grid-cols-5 gap-4 min-h-0 overflow-x-auto pb-4 no-scrollbar">
          {COLUMNS.map(column => (
            <div key={column.id} className="flex flex-col gap-3 min-w-[200px]">
              <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">{column.title}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-500 font-mono">
                    {prds.filter(p => p.columnId === column.id).length}
                  </span>
                </div>
              </div>
              
              <div className="flex-1 bg-zinc-900/30 rounded-xl border border-zinc-800/50 p-2 overflow-y-auto no-scrollbar">
                <SortableContext
                  id={column.id}
                  items={prds.filter(p => p.columnId === column.id).map(p => p.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="space-y-2 min-h-[150px]">
                    {prds
                      .filter(p => p.columnId === column.id)
                      .map(prd => (
                        <SortablePRDCard key={prd.id} prd={prd} onClick={onSelectPRD} />
                      ))}
                  </div>
                </SortableContext>
              </div>
            </div>
          ))}
        </div>

        <DragOverlay>
          {activePRD ? <SortablePRDCard prd={activePRD} /> : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
};

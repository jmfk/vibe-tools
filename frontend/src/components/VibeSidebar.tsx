import React, { useState, useEffect, useMemo } from 'react';
import { 
  Search, 
  FileText, 
  Database, 
  Folder, 
  AlertCircle, 
  ChevronRight,
  Pencil
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { invoke } from '@tauri-apps/api/tauri';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface Artifact {
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

interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

export const VibeSidebar = ({ 
  root, 
  onSelect, 
  onEdit,
  selectedPath, 
  accentColor, 
  isDark,
  showPrds = true,
  showSpecs = true
}: { 
  root: string, 
  onSelect: (artifact: Artifact) => void, 
  onEdit?: (artifact: Artifact) => void,
  selectedPath?: string, 
  accentColor?: string, 
  isDark: boolean,
  showPrds?: boolean,
  showSpecs?: boolean
}) => {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [prdTree, setPrdTree] = useState<TreeItem[]>([]);
  const [specTree, setSpecTree] = useState<TreeItem[]>([]);
  const [issueTree, setIssueTree] = useState<TreeItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (root) loadArtifacts();
  }, [root]);

  const loadArtifacts = async () => {
    try {
      const all: Artifact[] = [];
      const scan = async (dir: string, type: 'prd' | 'spec' | 'issue'): Promise<TreeItem[]> => {
        const items: TreeItem[] = [];
        try {
          const entries = await invoke<FileEntry[]>('list_directory', { path: dir });
          for (const f of entries) {
            if (f.is_dir) {
              const children = await scan(f.path, type);
              if (children.length > 0) {
                items.push({
                  name: f.name,
                  path: f.path,
                  is_dir: true,
                  children: children.sort((a, b) => (a.is_dir === b.is_dir ? a.name.localeCompare(b.name) : a.is_dir ? -1 : 1))
                });
              }
            } else if (f.name.endsWith('.md') || f.name.endsWith('.yaml')) {
              let artifactType = type;
              const artifact: Artifact = { 
                name: f.name, 
                path: f.path, 
                type: artifactType, 
                relPath: f.path.replace(root, '')
              };
              all.push(artifact);
              items.push({ name: f.name, path: f.path, is_dir: false, artifact: artifact, type: artifactType });
            }
          }
        } catch (e) {}
        return items;
      };

      const productDir = `${root}/product`;
      const productEntries = await invoke<FileEntry[]>('list_directory', { path: productDir });
      
      const specs: TreeItem[] = [];
      const prds: TreeItem[] = [];
      
      const prdGroups = ['inbox', 'backlog', 'next', 'history'];

      for (const f of productEntries) {
        if (!f.is_dir && (f.name.endsWith('.md') || f.name.endsWith('.yaml'))) {
          const artifact: Artifact = { 
            name: f.name, 
            path: f.path, 
            type: 'spec', 
            relPath: f.path.replace(root, '')
          };
          all.push(artifact);
          specs.push({ name: f.name, path: f.path, is_dir: false, artifact, type: 'spec' });
        }
      }

      for (const groupName of prdGroups) {
        const groupPath = `${productDir}/${groupName}`;
        const children = await scan(groupPath, 'prd');
        prds.push({
          name: groupName,
          path: groupPath,
          is_dir: true,
          children: children.sort((a, b) => (a.is_dir === b.is_dir ? a.name.localeCompare(b.name) : a.is_dir ? -1 : 1))
        });
      }

      setArtifacts(all);
      setPrdTree(prds);
      setSpecTree(specs);
      setIssueTree([]);
    } catch (err) {}
  };

  const filteredArtifacts = useMemo(() => {
    if (!searchQuery) return null;
    return artifacts.filter(a => 
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.relPath?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [artifacts, searchQuery]);

  return (
    <div className="flex flex-col gap-4">
      <div className="relative px-2">
        <Search className="absolute left-4 top-2.5 text-muted" size={12} />
        <input 
          type="text" 
          placeholder="Search..." 
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full bg-input border border-border rounded-md py-1.5 pl-8 pr-3 text-[10px] focus:outline-none focus:ring-1 focus:ring-accent/50 transition-colors"
        />
      </div>
      <div className="space-y-4 max-h-[60vh] overflow-y-auto no-scrollbar px-1">
        {filteredArtifacts ? (
          <div className="space-y-1">
                {filteredArtifacts
                  .filter(a => (showPrds && a.type === 'prd') || (showSpecs && a.type === 'spec'))
                  .map(artifact => (
                  <div key={artifact.path} className="group/item relative">
                    <button
                      onClick={() => onSelect(artifact)}
                      className={cn(
                        "w-full text-left px-2 py-1.5 rounded text-xs transition-colors truncate flex items-center gap-2 pr-8",
                        selectedPath === artifact.path 
                          ? (isDark ? "bg-zinc-800/50 border shadow-sm font-bold" : "bg-zinc-200/50 border shadow-sm font-bold")
                          : (isDark ? "text-muted hover:text-foreground hover:bg-zinc-800/20" : "text-muted hover:text-foreground hover:bg-zinc-200/20")
                      )}
                      style={selectedPath === artifact.path ? { borderColor: `${accentColor}40`, color: accentColor } : {}}
                    >
                      {artifact.type === 'prd' ? <FileText size={14} className="text-purple-500" /> :
                       artifact.type === 'spec' ? <Database size={14} className="text-accent" /> :
                       <AlertCircle size={14} className="text-emerald-500" />}
                      <span className="truncate">{artifact.name}</span>
                    </button>
                    {artifact.name.endsWith('.md') && (
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onEdit) {
                            onEdit(artifact);
                          } else {
                            invoke('run_vibe_command', { command: 'open', args: [artifact.path] });
                          }
                        }}
                        className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-accent/20 text-muted hover:text-accent opacity-0 group-hover/item:opacity-100 transition-all"
                        title="Edit PRD"
                      >
                        <Pencil size={10} />
                      </button>
                    )}
                  </div>
                ))}
          </div>
        ) : (
          <>
            {showSpecs && specTree.length > 0 && (
              <div>
                <div className="text-[9px] font-bold uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5 text-muted">
                  <div className="w-1 h-1 rounded-full bg-accent" />
                  System Specs
                </div>
                <SidebarTree items={specTree} selectedPath={selectedPath} onSelect={onSelect} onEdit={onEdit} accentColor={accentColor} isDark={isDark} />
              </div>
            )}
            {showPrds && (
              <div>
                <div className="text-[9px] font-bold uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5 text-muted">
                  <div className="w-1 h-1 rounded-full bg-purple-500" />
                  Product (PRDs)
                </div>
                <SidebarTree items={prdTree} selectedPath={selectedPath} onSelect={onSelect} onEdit={onEdit} accentColor={accentColor} isDark={isDark} />
              </div>
            )}
            {issueTree.length > 0 && (
              <div>
                <div className="text-[9px] font-bold uppercase tracking-widest mb-2 px-2 flex items-center gap-1.5 text-muted">
                  <div className="w-1 h-1 rounded-full bg-emerald-500" />
                  Issues
                </div>
                <SidebarTree items={issueTree} selectedPath={selectedPath} onSelect={onSelect} onEdit={onEdit} accentColor={accentColor} isDark={isDark} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

const SidebarTree = ({ 
  items, 
  level = 0, 
  selectedPath, 
  onSelect,
  onEdit,
  accentColor,
  isDark
}: { 
  items: TreeItem[], 
  level?: number, 
  selectedPath?: string, 
  onSelect: (artifact: Artifact) => void,
  onEdit?: (artifact: Artifact) => void,
  accentColor?: string,
  isDark: boolean
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
                className={cn(
                  "w-full text-left px-2 py-1.5 rounded text-xs transition-colors flex items-center gap-1.5 font-bold text-muted hover:text-foreground",
                  isDark ? "hover:bg-zinc-800/20" : "hover:bg-zinc-200/20"
                )}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
              >
                {expanded[item.path] ? <ChevronRight size={12} className="rotate-90" /> : <ChevronRight size={12} />}
                <Folder size={14} className="text-muted" />
                <span className="truncate flex-1">{item.name}</span>
                {item.is_dir && item.children && item.children.length > 0 && (
                  <span className="text-[9px] text-muted/60 font-mono mr-1">
                    {item.children.length}
                  </span>
                )}
              </button>
              {expanded[item.path] && item.children && (
                <SidebarTree 
                  items={item.children} 
                  level={level + 1} 
                  selectedPath={selectedPath} 
                  onSelect={onSelect} 
                  onEdit={onEdit}
                  accentColor={accentColor}
                  isDark={isDark}
                />
              )}
            </div>
          ) : (
            item.artifact && (
              <div className="group/item relative">
                <button
                  onClick={() => onSelect(item.artifact!)}
                  className={cn(
                    "w-full text-left px-2 py-1.5 rounded text-xs transition-colors truncate flex items-center gap-2 pr-8",
                    selectedPath === item.path 
                      ? (isDark ? "bg-zinc-800/50 border shadow-sm font-bold" : "bg-zinc-200/50 border shadow-sm font-bold")
                      : (isDark ? "text-muted hover:text-foreground hover:bg-zinc-800/20" : "text-muted hover:text-foreground hover:bg-zinc-200/20")
                  )}
                  style={{ 
                    paddingLeft: `${level * 12 + 24}px`,
                    ...(selectedPath === item.path ? { borderColor: `${accentColor}40`, color: accentColor } : {})
                  }}
                >
                {item.artifact.type === 'prd' ? <FileText size={14} className="text-purple-500" /> :
                 item.artifact.type === 'spec' ? <Database size={14} className="text-accent" /> :
                 <AlertCircle size={14} className="text-emerald-500" />}
                <span className="truncate">{item.name}</span>
              </button>
              {item.name.endsWith('.md') && (
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onEdit) {
                      onEdit(item.artifact!);
                    } else {
                      invoke('run_vibe_command', { command: 'open', args: [item.path] });
                    }
                  }}
                  className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-accent/20 text-muted hover:text-accent opacity-0 group-hover/item:opacity-100 transition-all"
                  title="Edit PRD"
                >
                  <Pencil size={10} />
                </button>
              )}
            </div>
            )
          )}
        </div>
      ))}
    </div>
  );
};

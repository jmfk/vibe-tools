import React from 'react';
import { LayoutDashboard, Folder } from 'lucide-react';
import { Accordion } from '../components/Accordion';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface Project {
  id: string;
  name: string;
  path: string;
  description?: string;
  last_active?: string;
}

interface ProjectsSidebarProps {
  projects: Project[];
  activeProjectId: string | null;
  onSwitchProject: (p: Project) => void | Promise<void>;
  isDark: boolean;
  accentColor: string;
}

export const ProjectsSidebar: React.FC<ProjectsSidebarProps> = ({
  projects,
  activeProjectId,
  onSwitchProject,
  isDark,
  accentColor
}) => {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto no-scrollbar">
        <Accordion title="All Projects" icon={LayoutDashboard} isDark={isDark}>
          <div className="space-y-1 mt-2">
            {projects.map(p => (
              <button
                key={p.id}
                onClick={() => onSwitchProject(p)}
                className={cn(
                  "w-full text-left px-2 py-1.5 rounded text-[11px] transition-colors truncate flex items-center gap-2",
                  activeProjectId === p.id 
                    ? (isDark ? "bg-zinc-800/20 border shadow-sm" : "bg-zinc-200/20 border shadow-sm")
                    : (isDark ? "text-muted hover:text-foreground hover:bg-zinc-800/10" : "text-muted hover:text-foreground hover:bg-zinc-200/10")
                )}
                style={activeProjectId === p.id ? { borderColor: `${accentColor}40`, color: accentColor } : {}}
              >
                <Folder size={12} className={activeProjectId === p.id ? "" : "text-muted"} style={activeProjectId === p.id ? { color: accentColor } : {}} />
                <span className="truncate">{p.name}</span>
              </button>
            ))}
          </div>
        </Accordion>
      </div>
    </div>
  );
};

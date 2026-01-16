import React from 'react';
import { Bug, Filter, Search } from 'lucide-react';
import { Accordion } from '../components/Accordion';

interface IssuesSidebarProps {
  isDark: boolean;
  accentColor: string;
}

export const IssuesSidebar: React.FC<IssuesSidebarProps> = ({
  isDark,
  accentColor
}) => {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto no-scrollbar">
        <Accordion title="Issues Filter" icon={Filter} isDark={isDark}>
          <div className="space-y-4 mt-2">
            <div className="relative px-2">
              <Search className="absolute left-4 top-2.5 text-muted" size={12} />
              <input 
                type="text" 
                placeholder="Search issues..." 
                className="w-full bg-input border border-border rounded-md py-1.5 pl-8 pr-3 text-[10px] focus:outline-none focus:ring-1 focus:ring-accent/50 transition-colors"
              />
            </div>
            <div className="space-y-1">
              {['All Issues', 'Open', 'Closed', 'My Issues'].map(f => (
                <button
                  key={f}
                  className="w-full text-left px-2 py-1.5 rounded text-xs text-muted hover:text-foreground hover:bg-zinc-800/20 transition-colors"
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </Accordion>
        
        <Accordion title="Severity" icon={Bug} isDark={isDark}>
          <div className="space-y-1 mt-2">
             {['Critical', 'High', 'Medium', 'Low'].map(s => (
                <button
                  key={s}
                  className="w-full text-left px-2 py-1.5 rounded text-xs text-muted hover:text-foreground hover:bg-zinc-800/20 transition-colors flex items-center gap-2"
                >
                  <div className={`w-1.5 h-1.5 rounded-full ${
                    s === 'Critical' ? 'bg-red-500' : 
                    s === 'High' ? 'bg-orange-500' : 
                    s === 'Medium' ? 'bg-yellow-500' : 'bg-blue-500'
                  }`} />
                  {s}
                </button>
              ))}
          </div>
        </Accordion>
      </div>
    </div>
  );
};

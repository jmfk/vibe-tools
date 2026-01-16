import React from 'react';
import { BarChart3, Clock, FileText } from 'lucide-react';
import { Accordion } from '../components/Accordion';

interface StatsSidebarProps {
  isDark: boolean;
  accentColor: string;
  period: string;
  onPeriodChange: (p: string) => void;
  loading: boolean;
}

export const StatsSidebar: React.FC<StatsSidebarProps> = ({
  isDark,
  accentColor,
  period,
  onPeriodChange,
  loading
}) => {
  const periods = [
    { id: 'today', label: 'Today' },
    { id: 'yesterday', label: 'Yesterday' },
    { id: 'week', label: 'This Week' },
    { id: 'prev-week', label: 'Last Week' },
    { id: 'month', label: 'This Month' },
    { id: 'prev-month', label: 'Last Month' },
    { id: '3-months', label: 'Last 3 Months' },
    { id: '6-months', label: 'Last 6 Months' },
    { id: 'year', label: 'This Year' },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto no-scrollbar">
        <Accordion title="Time Period" icon={Clock} isDark={isDark}>
          <div className="space-y-1 mt-2">
            {periods.map(p => (
              <button
                key={p.id}
                onClick={() => onPeriodChange(p.id)}
                disabled={loading}
                className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                  period === p.id 
                    ? 'bg-zinc-800/50 font-bold' 
                    : 'text-muted hover:text-foreground hover:bg-zinc-800/20'
                }`}
                style={period === p.id ? { color: accentColor } : {}}
              >
                {p.label}
              </button>
            ))}
          </div>
        </Accordion>

        <Accordion title="Reports" icon={FileText} isDark={isDark}>
          <div className="space-y-1 mt-2">
            {['Cost Analysis', 'Model Comparison', 'Project Breakdown', 'Token Usage'].map(r => (
              <button
                key={r}
                className="w-full text-left px-2 py-1.5 rounded text-xs text-muted hover:text-foreground hover:bg-zinc-800/20 transition-colors"
              >
                {r}
              </button>
            ))}
          </div>
        </Accordion>
      </div>
    </div>
  );
};

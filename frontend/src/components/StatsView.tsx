import React, { useState, useEffect, useMemo } from 'react';
import { 
  BarChart3, 
  Clock, 
  Coins, 
  Cpu, 
  Activity, 
  RefreshCw, 
  Calendar,
  Layers,
  Zap,
  TrendingUp,
  FileText
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface StatsData {
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_read: number;
  request_count: number;
  by_model: Record<string, any>;
  by_kind: Record<string, any>;
  by_phase: Record<string, any>;
  by_prd: Record<string, any>;
  by_agent: Record<string, any>;
}

interface StatsViewProps {
  accentColor: string;
}

const StatCard = ({ title, value, subValue, icon: Icon, accentColor }: { title: string, value: string, subValue?: string, icon: any, accentColor: string }) => (
  <div className="bg-panel border border-border rounded-xl p-5 flex flex-col gap-3 group hover:border-accent/30 transition-all">
    <div className="flex items-center justify-between">
      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-zinc-900 border border-zinc-800 group-hover:border-accent/20 transition-colors">
        <Icon size={16} style={{ color: accentColor }} />
      </div>
      <span className="text-[10px] font-bold text-muted uppercase tracking-widest">{title}</span>
    </div>
    <div>
      <div className="text-2xl font-bold text-foreground tracking-tight">{value}</div>
      {subValue && <div className="text-[10px] text-muted font-medium mt-1 uppercase tracking-wider">{subValue}</div>}
    </div>
  </div>
);

const ProgressBar = ({ label, value, max, color, subLabel }: { label: string, value: number, max: number, color: string, subLabel?: string }) => {
  const percentage = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-widest">
        <span className="text-zinc-300 truncate max-w-[150px]">{label}</span>
        <span className="text-muted">{subLabel || value.toLocaleString()}</span>
      </div>
      <div className="h-1.5 w-full bg-zinc-900 rounded-full overflow-hidden border border-zinc-800/50">
        <div 
          className="h-full transition-all duration-1000 ease-out" 
          style={{ width: `${percentage}%`, backgroundColor: color }} 
        />
      </div>
    </div>
  );
};

export const StatsView: React.FC<StatsViewProps> = ({ accentColor }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<StatsData | null>(null);
  const [period, setPeriod] = useState<string>('month');

  const fetchStats = async (p: string) => {
    setLoading(true);
    setPeriod(p);
    try {
      const flag = p === 'month' ? '--month' : 
                   p === 'prev-month' ? '--prev-month' : 
                   p === '3-months' ? '--last-3-months' : 
                   p === '6-months' ? '--last-6-months' : '--year';
      
      await invoke('run_vibe_command', { 
        command: 'stats', 
        args: [flag] 
      });
    } catch (e) {
      console.error("Error starting stats fetch:", e);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats('month');

    const unlisten = listen('vibe-server-event', (event: any) => {
      const payload = event.payload;
      if (payload.type === 'stats_result') {
        setData(payload as StatsData);
        setLoading(false);
      } else if (payload.type === 'result' && payload.code !== 0) {
        setLoading(false);
      }
    });

    return () => {
      unlisten.then(f => f());
    };
  }, []);

  const models = useMemo(() => {
    if (!data?.by_model) return [];
    return Object.entries(data.by_model)
      .map(([name, stats]) => ({ name, ...stats }))
      .sort((a, b) => b.cost - a.cost);
  }, [data]);

  const maxModelCost = useMemo(() => Math.max(...models.map(m => m.cost), 0), [models]);

  const prds = useMemo(() => {
    if (!data?.by_prd) return [];
    return Object.entries(data.by_prd)
      .map(([name, stats]) => ({ name, ...stats }))
      .sort((a, b) => b.cost - a.cost)
      .slice(0, 10);
  }, [data]);

  const maxPrdCost = useMemo(() => Math.max(...prds.map(p => p.cost), 0), [prds]);

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12">
      <div className="flex items-center justify-between border-b border-border pb-8">
        <div>
          <h2 className="text-3xl font-bold text-foreground flex items-center gap-3">
            <BarChart3 size={28} style={{ color: accentColor }} />
            Usage Statistics
          </h2>
          <p className="text-muted mt-2">Track your AI resource consumption and costs</p>
        </div>
        
        <div className="flex items-center gap-2 bg-panel border border-border p-1 rounded-xl">
          {[
            { id: 'month', label: 'Month' },
            { id: 'prev-month', label: 'Previous' },
            { id: '3-months', label: '3 Months' },
            { id: '6-months', label: '6 Months' },
            { id: 'year', label: 'Year' },
          ].map(p => (
            <button
              key={p.id}
              onClick={() => fetchStats(p.id)}
              disabled={loading}
              className={cn(
                "px-4 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap",
                period === p.id 
                  ? "bg-zinc-800 text-white shadow-sm" 
                  : "text-muted hover:text-foreground hover:bg-zinc-800/50"
              )}
              style={period === p.id ? { color: accentColor } : {}}
            >
              {p.label}
            </button>
          ))}
          <div className="w-px h-6 bg-border mx-1" />
          <button 
            onClick={() => fetchStats(period)}
            disabled={loading}
            className="p-2 text-muted hover:text-foreground transition-colors disabled:opacity-50"
          >
            <RefreshCw size={16} className={cn(loading && "animate-spin")} />
          </button>
        </div>
      </div>

      {!data && loading ? (
        <div className="h-96 flex flex-col items-center justify-center gap-4 text-muted">
          <RefreshCw size={48} className="animate-spin opacity-20" />
          <p className="text-sm font-medium animate-pulse">Aggregating usage data...</p>
        </div>
      ) : !data ? (
        <div className="h-96 flex flex-col items-center justify-center gap-4 text-muted border-2 border-dashed border-border rounded-3xl">
          <Activity size={48} className="opacity-10" />
          <p className="text-sm font-medium">No statistics data available for this period</p>
          <button 
            onClick={() => fetchStats(period)}
            className="px-6 py-2 rounded-xl bg-accent text-white font-bold text-sm transition-transform active:scale-95 shadow-lg"
            style={{ backgroundColor: accentColor }}
          >
            Retry Fetch
          </button>
        </div>
      ) : (
        <div className="space-y-8 animate-in fade-in duration-700">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard 
              title="Total Cost" 
              value={`$${data.total_cost.toFixed(2)}`} 
              subValue="USD" 
              icon={Coins} 
              accentColor="#f59e0b" 
            />
            <StatCard 
              title="Requests" 
              value={data.request_count.toLocaleString()} 
              subValue="Total Calls" 
              icon={Activity} 
              accentColor="#3b82f6" 
            />
            <StatCard 
              title="Input Tokens" 
              value={(data.total_input_tokens / 1000000).toFixed(1) + 'M'} 
              subValue="Total Input" 
              icon={Cpu} 
              accentColor="#8b5cf6" 
            />
            <StatCard 
              title="Output Tokens" 
              value={(data.total_output_tokens / 1000000).toFixed(1) + 'M'} 
              subValue="Total Output" 
              icon={Zap} 
              accentColor="#ec4899" 
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <section className="bg-panel border border-border rounded-2xl p-6 space-y-6 shadow-sm">
              <div className="flex items-center justify-between border-b border-border pb-4">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 uppercase tracking-widest">
                  <TrendingUp size={18} className="text-accent" style={{ color: accentColor }} />
                  Cost by Model
                </h3>
                <div className="text-[10px] font-bold text-muted uppercase">Distribution</div>
              </div>
              <div className="space-y-5">
                {models.map(m => (
                  <ProgressBar 
                    key={m.name}
                    label={m.name}
                    value={m.cost}
                    max={maxModelCost}
                    color={accentColor}
                    subLabel={`$${m.cost.toFixed(3)}`}
                  />
                ))}
              </div>
            </section>

            <section className="bg-panel border border-border rounded-2xl p-6 space-y-6 shadow-sm">
              <div className="flex items-center justify-between border-b border-border pb-4">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 uppercase tracking-widest">
                  <FileText size={18} className="text-purple-500" />
                  Top PRDs by Cost
                </h3>
                <div className="text-[10px] font-bold text-muted uppercase tracking-widest">Top 10</div>
              </div>
              <div className="space-y-5">
                {prds.length > 0 ? prds.map(p => (
                  <ProgressBar 
                    key={p.name}
                    label={p.name === 'N/A' ? 'General / Unknown' : p.name}
                    value={p.cost}
                    max={maxPrdCost}
                    color="#a855f7"
                    subLabel={`$${p.cost.toFixed(3)}`}
                  />
                )) : (
                  <div className="h-full flex items-center justify-center text-muted italic text-xs py-12">
                    No PRD-specific data available
                  </div>
                )}
              </div>
            </section>
          </div>

          <section className="bg-panel border border-border rounded-2xl p-6 shadow-sm">
             <div className="flex items-center justify-between border-b border-border pb-4 mb-6">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 uppercase tracking-widest">
                  <Layers size={18} className="text-emerald-500" />
                  Token Summary
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
                <div className="space-y-4">
                  <div className="text-[10px] font-bold text-muted uppercase tracking-widest">Cache Performance</div>
                  <div className="flex items-end gap-2">
                    <div className="text-3xl font-bold">{(data.total_cache_read / (data.total_input_tokens + data.total_cache_read) * 100 || 0).toFixed(1)}%</div>
                    <div className="text-[10px] text-emerald-500 font-bold mb-1.5 uppercase">Hit Rate</div>
                  </div>
                  <p className="text-[10px] text-muted leading-relaxed">Percentage of input tokens served from context cache.</p>
                </div>
                
                <div className="space-y-4">
                  <div className="text-[10px] font-bold text-muted uppercase tracking-widest">Output Density</div>
                  <div className="flex items-end gap-2">
                    <div className="text-3xl font-bold">{(data.total_output_tokens / data.request_count || 0).toFixed(0)}</div>
                    <div className="text-[10px] text-pink-500 font-bold mb-1.5 uppercase">Avg Tokens/Req</div>
                  </div>
                  <p className="text-[10px] text-muted leading-relaxed">Average amount of tokens generated per model request.</p>
                </div>

                <div className="space-y-4">
                  <div className="text-[10px] font-bold text-muted uppercase tracking-widest">Cost Efficiency</div>
                  <div className="flex items-end gap-2">
                    <div className="text-3xl font-bold">{(data.total_cost / data.request_count * 100 || 0).toFixed(2)}¢</div>
                    <div className="text-[10px] text-amber-500 font-bold mb-1.5 uppercase">Per Request</div>
                  </div>
                  <p className="text-[10px] text-muted leading-relaxed">Average cost in cents for a single AI agent interaction.</p>
                </div>
              </div>
          </section>
        </div>
      )}
    </div>
  );
};

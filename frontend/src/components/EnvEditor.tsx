import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Trash2, 
  Save, 
  RefreshCw, 
  AlertCircle,
  Shield,
  Key
} from 'lucide-react';
import { invoke } from '@tauri-apps/api/tauri';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface EnvVar {
  key: string;
  value: string;
}

interface EnvEditorProps {
  workspaceRoot: string;
  accentColor: string;
}

export const EnvEditor: React.FC<EnvEditorProps> = ({ workspaceRoot, accentColor }) => {
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEnv = async () => {
    setLoading(true);
    setError(null);
    try {
      const path = `${workspaceRoot}/.env`;
      const content = await invoke<string>('read_file_content', { path });
      
      const vars: EnvVar[] = content.split('\n')
        .filter(line => line.trim() && !line.startsWith('#') && line.includes('='))
        .map(line => {
          const [key, ...valueParts] = line.split('=');
          return {
            key: key.trim(),
            value: valueParts.join('=').trim().replace(/^["']|["']$/g, '')
          };
        });
      setEnvVars(vars);
    } catch (err) {
      console.error("Error loading .env file:", err);
      setEnvVars([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (workspaceRoot) {
      loadEnv();
    }
  }, [workspaceRoot]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const path = `${workspaceRoot}/.env`;
      const content = envVars
        .filter(v => v.key.trim())
        .map(v => `${v.key.trim()}=${v.value.trim()}`)
        .join('\n') + '\n';
      
      await invoke('write_file_content', { 
        path, 
        content
      });
    } catch (err: any) {
      setError(err.toString());
    } finally {
      setSaving(false);
    }
  };

  const addVar = () => {
    setEnvVars([...envVars, { key: '', value: '' }]);
  };

  const updateVar = (index: number, field: keyof EnvVar, value: string) => {
    const newVars = [...envVars];
    newVars[index][field] = value;
    setEnvVars(newVars);
  };

  const removeVar = (index: number) => {
    setEnvVars(envVars.filter((_, i) => i !== index));
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted">
        <RefreshCw size={32} className="animate-spin opacity-20" />
        <span className="text-sm font-medium">Loading environment variables...</span>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-4">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-zinc-800/50">
            <Shield size={20} style={{ color: accentColor }} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground">Environment Variables</h2>
            <p className="text-xs text-muted">Manage your project's environment variables in .env</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={loadEnv}
            className="p-2 text-muted hover:text-foreground transition-colors"
            title="Reload from file"
          >
            <RefreshCw size={18} />
          </button>
          <button 
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-bold text-white transition-all disabled:opacity-50 shadow-lg"
            style={{ backgroundColor: accentColor }}
          >
            {saving ? <RefreshCw size={16} className="animate-spin" /> : <Save size={16} />}
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="bg-panel border border-border rounded-xl overflow-hidden shadow-sm">
        <div className="grid grid-cols-[1fr,1.5fr,40px] gap-4 px-4 py-2 bg-zinc-900/50 border-b border-border text-[10px] font-bold text-muted uppercase tracking-widest">
          <div>Key</div>
          <div>Value</div>
          <div></div>
        </div>
        <div className="divide-y divide-border/50 max-h-[500px] overflow-y-auto scrollbar-thin">
          {envVars.length === 0 ? (
            <div className="p-8 text-center text-muted italic text-sm">
              No environment variables found.
            </div>
          ) : (
            envVars.map((v, i) => (
              <div key={i} className="grid grid-cols-[1fr,1.5fr,40px] gap-4 px-4 py-3 group hover:bg-zinc-800/20 transition-colors items-center">
                <div className="relative">
                  <Key size={12} className="absolute left-2 top-2.5 text-muted/50" />
                  <input 
                    type="text" 
                    value={v.key}
                    onChange={(e) => updateVar(i, 'key', e.target.value)}
                    placeholder="VAR_NAME"
                    className="w-full bg-input border border-border rounded-md pl-8 pr-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-accent/50 text-foreground transition-all"
                  />
                </div>
                <input 
                  type="text" 
                  value={v.value}
                  onChange={(e) => updateVar(i, 'value', e.target.value)}
                  placeholder="value"
                  className="w-full bg-input border border-border rounded-md px-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-accent/50 text-foreground transition-all"
                />
                <button 
                  onClick={() => removeVar(i)}
                  className="p-2 text-muted hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))
          )}
        </div>
        <div className="p-4 bg-zinc-900/30 border-t border-border">
          <button 
            onClick={addVar}
            className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-muted hover:text-foreground transition-colors"
          >
            <Plus size={14} />
            Add Variable
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 px-2 text-[10px] text-muted">
        <AlertCircle size={12} />
        Changes are saved to the .env file.
      </div>
    </div>
  );
};

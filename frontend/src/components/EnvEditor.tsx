import React, { useState, useEffect } from 'react';
import { 
  Save, 
  RefreshCw, 
  AlertCircle,
  Shield
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
  const [rawContent, setRawContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEnv = async () => {
    setLoading(true);
    setError(null);
    try {
      const path = `${workspaceRoot}/.env`;
      const content = await invoke<string>('read_file_content', { path });
      setRawContent(content);
    } catch (err) {
      console.error("Error loading .env file:", err);
      setRawContent('');
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
      await invoke('write_file_content', { 
        path, 
        content: rawContent
      });
    } catch (err: any) {
      setError(err.toString());
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted">
        <RefreshCw size={32} className="animate-spin opacity-20" />
        <span className="text-sm font-medium">Loading .env file...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-zinc-800/50">
            <Shield size={20} style={{ color: accentColor }} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground">Environment Variables</h2>
            <p className="text-xs text-muted">Directly editing .env file</p>
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
            {saving ? "Saving..." : "Save .env"}
          </button>
        </div>
      </div>

      {error && (
        <div className="m-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="flex-1 p-4">
        <textarea
          value={rawContent}
          onChange={(e) => setRawContent(e.target.value)}
          className="w-full h-full bg-zinc-900 border border-zinc-800 rounded-xl p-6 font-mono text-sm text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-700 transition-all resize-none scrollbar-thin"
          placeholder="# Environment Variables&#10;KEY=VALUE"
          spellCheck={false}
        />
      </div>

      <div className="flex items-center gap-2 px-6 py-3 border-t border-zinc-800 text-[10px] text-muted bg-zinc-900/30">
        <AlertCircle size={12} />
        Changes are saved directly to the .env file in your project root.
      </div>
    </div>
  );
};

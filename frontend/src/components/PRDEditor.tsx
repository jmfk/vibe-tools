import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Pencil,
  Eye,
  Check,
  Copy,
  Save,
  ArrowLeft,
  AlertCircle,
  Bold,
  Italic,
  Heading1,
  Heading2,
  List,
  Link as LinkIcon,
  ChevronDown,
  Type,
  Minus
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { PRD } from './PlannerBoard';
import { VanillaPRDEditor } from './VanillaPRDEditor';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const ToolbarButton = React.memo(({ onClick, icon, label, isDark, disabled }: {
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  isDark?: boolean;
  disabled?: boolean;
}) => (
  <button
    onMouseDown={(e) => {
      // Prevent focus from leaving the editor when clicking a toolbar button
      e.preventDefault();
      e.stopPropagation();
    }}
    onClick={(e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) onClick();
    }}
    disabled={disabled}
    className={cn(
      "p-1.5 rounded transition-all flex items-center gap-1",
      isDark ? "hover:bg-zinc-800 text-muted hover:text-foreground" : "hover:bg-zinc-200 text-muted hover:text-foreground",
      disabled && "opacity-20 cursor-not-allowed hover:bg-transparent"
    )}
    title={label}
  >
    {icon}
  </button>
));

export const PRDEditor = React.memo(({
  prd,
  initialContent,
  onSave,
  onCancel,
  accentColor = '#10b981',
  isDark,
  deleted = false
}: { 
  prd: PRD;
  initialContent: string;
  onSave: (content: string) => void;
  onCancel: () => void;
  accentColor?: string;
  isDark?: boolean;
  deleted?: boolean;
}) => {
  const [isPreview, setIsPreview] = useState(false);
  const [copied, setCopied] = useState(false);
  const [hasExternalChanges, setHasExternalChanges] = useState(false);
  const [lastSyncedContent, setLastSyncedContent] = useState(initialContent);
  
  const editorRef = useRef<VanillaPRDEditor | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize and manage the vanilla editor
  useEffect(() => {
    if (!isPreview && containerRef.current && !editorRef.current) {
      editorRef.current = new VanillaPRDEditor(
        containerRef.current,
        initialContent,
        (content) => {
          setLastSyncedContent(content);
          onSave(content);
        },
        accentColor,
        isDark
      );
    }

    return () => {
      if (editorRef.current) {
        editorRef.current.destroy();
        editorRef.current = null;
      }
    };
  }, [isPreview, accentColor, isDark]);

  // Handle external updates
  useEffect(() => {
    if (initialContent !== lastSyncedContent) {
      if (editorRef.current?.getIsFocused()) {
        setHasExternalChanges(true);
      } else {
        setLastSyncedContent(initialContent);
        editorRef.current?.setContent(initialContent);
        setHasExternalChanges(false);
      }
    }
  }, [initialContent, lastSyncedContent]);

  const handleManualSync = () => {
    if (editorRef.current) {
      editorRef.current.setContent(initialContent);
      setLastSyncedContent(initialContent);
      setHasExternalChanges(false);
    }
  };

  const handleSave = () => {
    if (editorRef.current) {
      const content = editorRef.current.getContent();
      setLastSyncedContent(content);
      onSave(content);
    }
  };

  const handleCopy = () => {
    const content = editorRef.current ? editorRef.current.getContent() : initialContent;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="h-full flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button 
            onClick={onCancel} 
            className={cn(
              "p-2 rounded-lg text-muted transition-colors", 
              isDark ? "hover:bg-zinc-800" : "hover:bg-zinc-200"
            )}
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold" style={{ color: accentColor }}>{prd.id}</span>
              <span className="text-[10px] text-muted font-mono">{prd.filename}</span>
              {hasExternalChanges && (
                <button 
                  onClick={handleManualSync}
                  className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-500 text-[9px] font-bold uppercase tracking-wider hover:bg-orange-500/20 transition-colors"
                  title="External changes detected. Click to sync."
                >
                  <AlertCircle size={10} />
                  External Diff
                </button>
              )}
            </div>
            <h3 className="text-sm font-bold text-foreground">{prd.title}</h3>
          </div>
        </div>
        {deleted && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-[10px] font-bold uppercase tracking-wider animate-pulse">
            <AlertCircle size={14} />
            Deleted from Disk
          </div>
        )}
        <div className="flex items-center gap-2">
          <div className="flex bg-panel border border-border rounded-lg p-1 mr-2">
            <button 
              onClick={() => setIsPreview(!isPreview)} 
              className={cn(
                "p-1.5 rounded transition-all flex items-center gap-2 px-3 text-[10px] font-bold uppercase tracking-wider", 
                isPreview 
                  ? (isDark ? "bg-zinc-800 text-accent" : "bg-zinc-200 text-accent") 
                  : "text-muted hover:text-foreground"
              )}
            >
              {isPreview ? <Pencil size={14} /> : <Eye size={14} />} 
              {isPreview ? "Edit" : "Preview"}
            </button>
          </div>

          <button 
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleCopy} 
            className={cn(
              "p-2 rounded-lg text-muted transition-colors mr-2", 
              isDark ? "hover:bg-zinc-800" : "hover:bg-zinc-200"
            )}
          >
            {copied ? <Check size={18} className="text-green-500" /> : <Copy size={18} />}
          </button>
          <button 
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleSave} 
            className="px-4 py-2 bg-accent text-white rounded-lg text-xs font-bold transition-all shadow-lg hover:brightness-110" 
            style={{ backgroundColor: accentColor }}
          >
            <Save size={14} className="inline mr-2" />
            Save PRD
          </button>
        </div>
      </div>

      <div className="flex-1 bg-panel border border-border rounded-xl overflow-hidden flex flex-col">
        {isPreview ? (
          <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
            <div className="max-w-4xl mx-auto">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]} 
                  rehypePlugins={[rehypeHighlight]}
                >
                  {lastSyncedContent}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 relative group/vanilla flex flex-col overflow-hidden">
            <div className="max-w-4xl mx-auto w-full h-full flex flex-col">
              {/* Visual indicator for Vanilla JS Engine */}
              <div className="absolute top-2 right-4 text-[8px] font-mono text-emerald-500/30 group-hover/vanilla:text-emerald-500/60 uppercase tracking-widest select-none pointer-events-none transition-colors z-[11]">
                Vanilla JS Engine Area
              </div>
              <div 
                ref={containerRef}
                className={cn(
                  "prd-editor-container flex-1 min-h-0 prose prose-sm max-w-none dark:prose-invert focus:outline-none",
                  isDark ? "prose-invert" : ""
                )}
              />
            </div>
          </div>
        )}
      </div>

      <style>{`
        .prd-editor-container {
          font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        .prd-editor-container h1 { font-size: 1.875rem; font-weight: 700; margin-top: 2rem; margin-bottom: 1rem; }
        .prd-editor-container h2 { font-size: 1.5rem; font-weight: 700; margin-top: 1.5rem; margin-bottom: 0.75rem; }
        .prd-editor-container h3 { font-size: 1.25rem; font-weight: 700; margin-top: 1.25rem; margin-bottom: 0.5rem; }
        .prd-editor-container p { margin-bottom: 1rem; line-height: 1.6; }
        .prd-editor-container li { margin-bottom: 0.25rem; }
        .prd-editor-container blockquote { border-left: 4px solid ${accentColor}40; padding-left: 1rem; font-style: italic; color: #71717a; margin: 1rem 0; }
        .prd-editor-container code { background-color: rgba(0,0,0,0.05); padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; font-size: 0.875em; }
        .dark .prd-editor-container code { background-color: rgba(255,255,255,0.1); }
        .prd-editor-container pre { background-color: #18181b; color: #e4e4e7; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; margin: 1rem 0; }
        .prd-editor-container pre code { background-color: transparent; padding: 0; color: inherit; }
        
        .prd-comment { color: #f97316; font-family: ui-monospace; font-size: 0.875rem; background: #f9731610; padding: 2px 4px; border-radius: 4px; margin: 4px 0; }
        .prd-details-open, .prd-details-close { color: ${accentColor}; font-family: ui-monospace; font-size: 0.75rem; opacity: 0.5; user-select: none; }
        .prd-details-container { border: 1px solid ${accentColor}40; border-radius: 8px; margin: 1rem 0; overflow: hidden; }
        .prd-summary { font-weight: bold; color: ${accentColor}; background: ${accentColor}10; padding: 4px 12px; border-bottom: 1px solid ${accentColor}20; cursor: text; margin: 0 !important; }
        .prd-details-content { padding: 12px; min-height: 20px; }
        .prd-checklist-item { list-style: none; display: flex; align-items: center; gap: 8px; }
        .prd-checklist-item input { width: 14px; height: 14px; cursor: pointer; }
        .prd-math-block { background: #18181b; color: #10b981; padding: 1rem; border-radius: 0.5rem; font-family: ui-monospace, monospace; margin: 1rem 0; text-align: center; }
        .prd-yaml { border: 1px dashed #3f3f46; padding: 1rem; border-radius: 0.5rem; font-family: ui-monospace, monospace; color: #71717a; margin-bottom: 2rem; background: #f4f4f510; }
        .dark .prd-yaml { background: #18181b50; }
        table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
        th, td { border: 1px solid #3f3f4640; padding: 8px; text-align: left; }
        th { background: #f4f4f5; font-weight: bold; }
        .dark th { background: #18181b; }
      `}</style>
    </div>
  );
});

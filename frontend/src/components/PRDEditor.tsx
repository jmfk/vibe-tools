import React, { useState, useEffect, useRef } from 'react';
import {
  Pencil,
  Eye,
  Check,
  Copy,
  Save,
  ArrowLeft,
  Bold,
  Italic,
  Heading1,
  Heading2,
  Heading3,
  Heading4,
  Heading5,
  Heading6,
  Type,
  Link,
  Strikethrough,
  Code,
  ListTodo,
  Quote,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { PRD } from './PlannerBoard';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ToolbarButtonProps {
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  isDark?: boolean;
}

const ToolbarButton = ({ onClick, icon, label, isDark }: ToolbarButtonProps) => (
  <button
    onClick={(e) => {
      e.preventDefault();
      e.stopPropagation();
      onClick();
    }}
    className={cn(
      "p-1.5 rounded transition-all flex items-center gap-1",
      isDark ? "hover:bg-zinc-800 text-muted hover:text-foreground" : "hover:bg-zinc-200 text-muted hover:text-foreground"
    )}
    title={label}
  >
    {icon}
  </button>
);

const InlineRowEditor = ({ 
  initialContent, 
  onChange, 
  onKeyDown, 
  onBlur,
  className,
  placeholder,
  isPlainText
}: { 
  initialContent: string, 
  onChange: (text: string) => void, 
  onKeyDown: (e: React.KeyboardEvent) => void, 
  onBlur: () => void,
  className?: string,
  placeholder?: string,
  isPlainText?: boolean
}) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) {
      if (isPlainText) {
        if (ref.current.textContent !== initialContent) {
          ref.current.textContent = initialContent;
        }
      } else {
        if (ref.current.innerHTML !== initialContent) {
          ref.current.innerHTML = initialContent;
        }
      }
    }
  }, []);

  useEffect(() => {
    if (ref.current) {
      ref.current.focus();
      // Move cursor to end
      const range = document.createRange();
      const selection = window.getSelection();
      range.selectNodeContents(ref.current);
      range.collapse(false);
      selection?.removeAllRanges();
      selection?.addRange(range);
    }
  }, []);

  return (
    <div
      ref={ref}
      contentEditable
      suppressContentEditableWarning
      className={cn(
        "flex-1 bg-transparent p-0 focus:outline-none",
        className
      )}
      onInput={(e) => {
        onChange(isPlainText ? e.currentTarget.textContent || '' : e.currentTarget.innerHTML);
      }}
      onKeyDown={onKeyDown}
      onBlur={onBlur}
      data-placeholder={placeholder}
    />
  );
};

interface ContextMenuItemProps {
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  shortcut?: string;
  isDark?: boolean;
}

const ContextMenuItem = ({ onClick, icon, label, shortcut, isDark }: ContextMenuItemProps) => (
  <button 
    onClick={(e) => {
      e.preventDefault();
      e.stopPropagation();
      onClick();
    }}
    className={cn(
      "w-full flex items-center justify-between px-3 py-1.5 text-[12px] transition-colors rounded-md",
      isDark ? "hover:bg-accent text-foreground hover:text-white" : "hover:bg-accent text-foreground hover:text-white"
    )}
  >
    <div className="flex items-center gap-2">
      <div className="w-4 h-4 flex items-center justify-center opacity-70">
        {icon}
      </div>
      <span>{label}</span>
    </div>
    {shortcut && (
      <span className="text-[10px] opacity-40 font-mono ml-4">{shortcut}</span>
    )}
  </button>
);

export const PRDEditor = ({
  prd,
  content,
  onContentChange,
  onSave,
  onCancel,
  accentColor,
  isDark
}: {
  prd: PRD;
  content: string;
  onContentChange: (content: string) => void;
  onSave: () => void;
  onCancel: () => void;
  accentColor?: string;
  isDark?: boolean;
}) => {
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);
  const [isPreview, setIsPreview] = useState(false);
  const [copied, setCopied] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number, y: number, index: number } | null>(null);
  const lines = content.split('\n');
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  const handleContextMenu = (e: React.MouseEvent, index: number) => {
    e.preventDefault();
    const x = e.clientX;
    const y = e.clientY;
    
    // Simple boundary check
    const menuWidth = 200;
    const menuHeight = 400;
    const adjustedX = x + menuWidth > window.innerWidth ? x - menuWidth : x;
    const adjustedY = y + menuHeight > window.innerHeight ? y - menuHeight : y;

    setContextMenu({ x: adjustedX, y: adjustedY, index });
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target as Node)) {
        setContextMenu(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLineChange = (index: number, newText: string) => {
    const newLines = [...lines];
    newLines[index] = newText;
    onContentChange(newLines.join('\n'));
  };

  const mdToHtml = (md: string) => {
    return md
      .replace(/(^|[^\\])\*\*\*(.*?)\*\*\*/g, '$1<b><i>$2</i></b>')
      .replace(/(^|[^\\])\*\*(.*?)\*\*/g, '$1<b>$2</b>')
      .replace(/(^|[^\\])_(.*?)_/g, '$1<i>$2</i>')
      .replace(/(^|[^\\])~~(.*?)~~/g, '$1<strike>$2</strike>')
      .replace(/(^|[^\\])`([^`]+)`/g, '$1<code>$2</code>')
      .replace(/(^|[^\\])\[(.*?)\]\((.*?)\)/g, '$1<a href="$3">$2</a>');
  };

  const htmlToMd = (html: string) => {
    const clean = (text: string) => text.replace(/<[^>]*>/g, '').trim();

    return html
      // 1. Convert tags to markdown with enforced exterior spaces and trimmed interior
      .replace(/<b[^>]*><i>\s*(.*?)\s*<\/i><\/b>/g, (_, p1) => ` ***${clean(p1)}*** `)
      .replace(/<i[^>]*><b>\s*(.*?)\s*<\/b><\/i>/g, (_, p1) => ` ***${clean(p1)}*** `)
      .replace(/<b[^>]*>\s*(.*?)\s*<\/b>/g, (_, p1) => ` **${clean(p1)}** `)
      .replace(/<strong[^>]*>\s*(.*?)\s*<\/strong>/g, (_, p1) => ` **${clean(p1)}** `)
      .replace(/<i[^>]*>\s*(.*?)\s*<\/i>/g, (_, p1) => ` _${clean(p1)}_ `)
      .replace(/<em[^>]*>\s*(.*?)\s*<\/em>/g, (_, p1) => ` _${clean(p1)}_ `)
      .replace(/<strike[^>]*>\s*(.*?)\s*<\/strike>/g, (_, p1) => ` ~~${clean(p1)}~~ `)
      .replace(/<s[^>]*>\s*(.*?)\s*<\/s>/g, (_, p1) => ` ~~${clean(p1)}~~ `)
      .replace(/<code[^>]*>\s*(.*?)\s*<\/code>/g, (_, p1) => ` \`${clean(p1)}\` `)
      .replace(/<a[^>]*href="(.*?)"[^>]*>\s*(.*?)\s*<\/a>/g, (_, p1, p2) => ` [${clean(p2)}](${p1}) `)
      
      // 2. Standard HTML entity and tag cleanup
      .replace(/<br\s*\/?>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/<div>(.*?)<\/div>/g, '$1') 
      .replace(/<p>(.*?)<\/p>/g, '$1')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&')
      
      // 3. Remove empty markers
      .replace(/\*\*\*[\s]*\*\*\*/g, '') 
      .replace(/\*\*[\s]*\*\*/g, '')    
      .replace(/_[\s]*_/g, '')          
      .replace(/~~[\s]*~~/g, '')        
      .replace(/`[\s]*`/g, '')          
      .replace(/\[[\s]*\]\((.*?)\)/g, '') 

      // 4. Final whitespace normalization
      .replace(/(\*\*\*|\*\*|__|___|_|~~|`|\]\(\S+\))\s*(\*\*\*|\*\*|__|___|_|~~|`|\[)/g, '$1 $2')
      .replace(/\s+/g, ' ') 
      .trim();
  };

  const parseLine = (line: string) => {
    const headerMatch = line.match(/^(#+)\s(.*)/);
    if (headerMatch) {
      return { type: 'header' as const, prefix: headerMatch[1] + ' ', content: headerMatch[2], suffix: '' };
    }
    const listMatch = line.match(/^(\s*[-*+]\s+)(.*)/);
    if (listMatch) {
      return { type: 'list' as const, prefix: listMatch[1], content: listMatch[2], suffix: '' };
    }
    const summaryMatch = line.match(/^<summary>(.*)<\/summary>$/);
    if (summaryMatch) {
      return { type: 'summary' as const, prefix: '<summary>', content: summaryMatch[1], suffix: '</summary>' };
    }
    const detailsMatch = line.match(/^<details>$/);
    if (detailsMatch) {
      return { type: 'details-open' as const, prefix: '<details>', content: '', suffix: '' };
    }
    const detailsCloseMatch = line.match(/^<\/details>$/);
    if (detailsCloseMatch) {
      return { type: 'details-close' as const, prefix: '</details>', content: '', suffix: '' };
    }
    const codeFenceMatch = line.match(/^```(\w*)$/);
    if (codeFenceMatch) {
      return { type: 'code-fence' as const, prefix: '```', content: codeFenceMatch[1], suffix: '' };
    }
    const quoteMatch = line.match(/^>\s(.*)/);
    if (quoteMatch) {
      return { type: 'quote' as const, prefix: '> ', content: quoteMatch[1], suffix: '' };
    }
    const hrMatch = line.match(/^(---|---|\*\*\*|___)$/);
    if (hrMatch) {
      return { type: 'hr' as const, prefix: '', content: hrMatch[1], suffix: '' };
    }
    const checkMatch = line.match(/^(\s*[-*+]\s+\[([ x])\]\s+)(.*)/);
    if (checkMatch) {
      return { type: 'checklist' as const, prefix: checkMatch[1], content: checkMatch[3], isChecked: checkMatch[2] === 'x', suffix: '' };
    }
    const commentMatch = line.match(/^<!--\s*(.*)\s*-->$/);
    if (commentMatch) {
      return { type: 'comment' as const, prefix: '<!-- ', content: commentMatch[1], suffix: ' -->' };
    }
    return { type: 'paragraph' as const, prefix: '', content: line, suffix: '' };
  };

  const getLineContexts = () => {
    let isInsideCodeBlock = false;
    return lines.map(line => {
      const parsed = parseLine(line);
      const wasInside = isInsideCodeBlock;
      if (parsed.type === 'code-fence') {
        isInsideCodeBlock = !isInsideCodeBlock;
      }
      return { isInsideCodeBlock: wasInside || (parsed.type === 'code-fence') };
    });
  };

  const lineContexts = getLineContexts();

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.ctrlKey || e.metaKey) {
      if (e.key === 'b') {
        e.preventDefault();
        if (!lineContexts[index].isInsideCodeBlock) applyFormat(index, '**', '**');
      } else if (e.key === 'i') {
        e.preventDefault();
        if (!lineContexts[index].isInsideCodeBlock) applyFormat(index, '_', '_');
      } else if (e.key === 'k') {
        e.preventDefault();
        if (!lineContexts[index].isInsideCodeBlock) applyFormat(index, 'link', '');
      } else if (e.key === 'l') {
        e.preventDefault();
        if (!lineContexts[index].isInsideCodeBlock) toggleList(index);
      } else if (e.key >= '1' && e.key <= '6') {
        e.preventDefault();
        if (!lineContexts[index].isInsideCodeBlock) {
          const level = parseInt(e.key);
          applyHeader(index, level);
        }
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const currentLine = lines[index];
      const parsed = parseLine(currentLine);
      const context = lineContexts[index];
      const newLines = [...lines];
      let nextLinePrefix = '';

      if (context.isInsideCodeBlock && parsed.type !== 'code-fence') {
        nextLinePrefix = ''; // Just a new line in code block
      } else if (parsed.type === 'list') {
        if (parsed.content.trim() === '') {
          // Empty list item: clear prefix and become paragraph
          newLines[index] = '';
          nextLinePrefix = '';
        } else {
          // Non-empty list item: continue list
          nextLinePrefix = parsed.prefix;
        }
      } else if (parsed.type === 'header') {
        // After header: always paragraph
        nextLinePrefix = '';
      } else if (parsed.type === 'details-open') {
        nextLinePrefix = '<summary>Metadata</summary>';
      } else if (parsed.type === 'summary') {
        nextLinePrefix = ''; // Start content after summary
      }

      newLines.splice(index + 1, 0, nextLinePrefix);
      onContentChange(newLines.join('\n'));
      setFocusedIndex(index + 1);
    } else if (e.key === 'Backspace') {
      const currentLine = lines[index];
      const parsed = parseLine(currentLine);
      
      if (parsed.content === '' && (parsed.type === 'list' || parsed.type === 'header' || parsed.type === 'summary')) {
        // Remove prefix/marker and convert to paragraph instead of deleting line
        e.preventDefault();
        handleLineChange(index, '');
      } else if (currentLine === '' && lines.length > 1) {
        e.preventDefault();
        const newLines = lines.filter((_, i) => i !== index);
        onContentChange(newLines.join('\n'));
        setFocusedIndex(index > 0 ? index - 1 : 0);
      }
    } else if (e.key === 'ArrowUp') {
      if (index > 0) {
        e.preventDefault();
        let nextIndex = index - 1;
        while (nextIndex > 0 && (parseLine(lines[nextIndex]).type === 'details-open' || parseLine(lines[nextIndex]).type === 'details-close')) {
          nextIndex--;
        }
        // If the top line is a details tag, don't move focus there unless it's the only option
        const finalType = parseLine(lines[nextIndex]).type;
        if (finalType !== 'details-open' && finalType !== 'details-close') {
          setFocusedIndex(nextIndex);
        }
      }
    } else if (e.key === 'ArrowDown') {
      if (index < lines.length - 1) {
        e.preventDefault();
        let nextIndex = index + 1;
        while (nextIndex < lines.length - 1 && (parseLine(lines[nextIndex]).type === 'details-open' || parseLine(lines[nextIndex]).type === 'details-close')) {
          nextIndex++;
        }
        const finalType = parseLine(lines[nextIndex]).type;
        if (finalType !== 'details-open' && finalType !== 'details-close') {
          setFocusedIndex(nextIndex);
        }
      }
    }
  };

  const applyFormat = (index: number, prefix: string, suffix: string) => {
    if (prefix === '**') {
      if (document.queryCommandState('italic')) document.execCommand('italic', false);
      if (document.queryCommandState('strikeThrough')) document.execCommand('strikeThrough', false);
      document.execCommand('bold', false);
    } else if (prefix === '_') {
      if (document.queryCommandState('bold')) document.execCommand('bold', false);
      if (document.queryCommandState('strikeThrough')) document.execCommand('strikeThrough', false);
      document.execCommand('italic', false);
    } else if (prefix === '~~') {
      if (document.queryCommandState('bold')) document.execCommand('bold', false);
      if (document.queryCommandState('italic')) document.execCommand('italic', false);
      document.execCommand('strikeThrough', false);
    } else if (prefix === '`') {
      const selection = window.getSelection();
      if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        if (range.toString().length > 0) {
          const code = document.createElement('code');
          code.textContent = range.toString();
          range.deleteContents();
          range.insertNode(code);
          const editor = range.startContainer.parentElement?.closest('[contenteditable]');
          if (editor) {
            editor.dispatchEvent(new Event('input', { bubbles: true }));
          }
        }
      }
    } else if (prefix === 'link') {
      const url = prompt('Enter URL:');
      if (url) {
        const selection = window.getSelection();
        if (selection && selection.rangeCount > 0) {
          const range = selection.getRangeAt(0);
          const text = range.toString() || url;
          const a = document.createElement('a');
          a.href = url;
          a.textContent = text;
          range.deleteContents();
          range.insertNode(a);
          const editor = range.startContainer.parentElement?.closest('[contenteditable]');
          if (editor) {
            editor.dispatchEvent(new Event('input', { bubbles: true }));
          }
        }
      }
    } else if (prefix === 'quote') {
      const parsed = parseLine(lines[index]);
      if (parsed.type === 'quote') {
        handleLineChange(index, parsed.content);
      } else {
        handleLineChange(index, '> ' + lines[index]);
      }
    }
  };

  const applyHeader = (index: number, level: number) => {
    const currentLine = lines[index];
    const parsed = parseLine(currentLine);
    const headerPrefix = '#'.repeat(level) + ' ';
    handleLineChange(index, headerPrefix + parsed.content + parsed.suffix);
  };

  const toggleList = (index: number) => {
    const currentLine = lines[index];
    const parsed = parseLine(currentLine);
    if (parsed.type === 'list' || parsed.type === 'checklist') {
      handleLineChange(index, parsed.content + parsed.suffix);
    } else {
      handleLineChange(index, '- ' + parsed.content + parsed.suffix);
    }
  };

  const toggleChecklist = (index: number) => {
    const currentLine = lines[index];
    const parsed = parseLine(currentLine);
    if (parsed.type === 'checklist') {
      const newChecked = !parsed.isChecked;
      handleLineChange(index, `- [${newChecked ? 'x' : ' '}] ` + parsed.content + parsed.suffix);
    } else {
      handleLineChange(index, '- [ ] ' + parsed.content + parsed.suffix);
    }
  };

  const insertDetails = (index: number) => {
    const newLines = [...lines];
    const targetIndex = index === -1 ? lines.length : index + 1;
    newLines.splice(targetIndex, 0, '<details>', '<summary>New Section</summary>', '', '</details>');
    onContentChange(newLines.join('\n'));
    setFocusedIndex(targetIndex + 1);
  };

  const removeDetails = (index: number) => {
    let start = -1;
    let end = -1;
    
    for (let i = index; i >= 0; i--) {
      if (lines[i].trim() === '<details>') {
        start = i;
        break;
      }
      if (i !== index && lines[i].trim() === '</details>') break;
    }
    
    if (start !== -1) {
      for (let i = start; i < lines.length; i++) {
        if (lines[i].trim() === '</details>') {
          end = i;
          break;
        }
      }
    }
    
    if (start !== -1 && end !== -1) {
      const newLines = lines.filter((_, i) => i < start || i > end);
      onContentChange(newLines.join('\n'));
      setFocusedIndex(Math.max(0, start - 1));
    }
  };

  const renderLinesStartIdx = (idx: number) => {
    let start = idx;
    while (start > 0 && lineContexts[start - 1] && lineContexts[start - 1].isInsideCodeBlock) {
      start--;
    }
    return start;
  };

  const renderLine = (i: number, isPartofBlock: boolean) => {
    const line = lines[i];
    const context = lineContexts[i];
    const parsed = parseLine(line);

    return (
      <div
        key={i}
        className={cn(
          "group relative min-h-[1.5rem] px-2 rounded-md border border-transparent",
          !isPreview && (focusedIndex === i ? (isDark ? "bg-zinc-800/50" : "bg-zinc-100") : (parsed.type === 'details-open' || parsed.type === 'details-close' ? "" : "hover:bg-zinc-800/20")),
          !isPartofBlock && "my-0.5",
          isPartofBlock && "font-mono py-0",
          !isPartofBlock && context.isInsideCodeBlock && (isDark ? "bg-zinc-900/50 font-mono" : "bg-zinc-100 font-mono")
        )}
        onClick={(e) => {
          if (isPreview) return;
          if (parsed.type === 'details-open' || parsed.type === 'details-close') return;
          e.stopPropagation();
          setFocusedIndex(i);
        }}
        onContextMenu={(e) => !isPreview && handleContextMenu(e, i)}
      >
        {!isPreview && focusedIndex === i ? (
          <div className="flex items-start gap-2 w-full">
            {(() => {
              let visualMarker = null;
              let textStyle = "text-sm leading-relaxed";

              if (context.isInsideCodeBlock) {
                textStyle = "font-mono text-xs opacity-90";
                if (parsed.type === 'code-fence') {
                  visualMarker = <div className="text-accent font-bold opacity-50">#</div>;
                }
              } else if (parsed.type === 'list') {
                visualMarker = <div className="mt-2 w-1.5 h-1.5 rounded-full bg-muted shrink-0" />;
              } else if (parsed.type === 'checklist') {
                visualMarker = (
                  <div
                    className={cn(
                      "mt-1 w-4 h-4 border rounded flex items-center justify-center cursor-pointer transition-colors",
                      parsed.isChecked ? "bg-accent border-accent" : "bg-transparent border-border hover:border-accent"
                    )}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleChecklist(i);
                    }}
                  >
                    {parsed.isChecked && <Check size={10} className="text-white" />}
                  </div>
                );
              } else if (parsed.type === 'quote') {
                visualMarker = <div className="w-1 self-stretch bg-accent opacity-30 rounded-full" />;
                textStyle = "italic text-muted pl-2";
              } else if (parsed.type === 'hr') {
                visualMarker = <div className="w-full h-px bg-border my-4 absolute left-0 right-0 top-1/2 -translate-y-1/2 pointer-events-none" />;
                textStyle = "text-center font-mono opacity-20 hover:opacity-100 transition-opacity relative z-10 bg-panel px-4 text-xs";
              } else if (parsed.type === 'details-open' || parsed.type === 'details-close') {
                return (
                  <div 
                    className={cn(
                      "flex-1 flex items-center gap-2 py-1 px-2 rounded border select-none transition-colors",
                      isDark ? "bg-zinc-800/20 border-border/30" : "bg-zinc-100/50 border-border/50",
                      "opacity-60 pointer-events-none"
                    )}
                  >
                    <div className="text-accent opacity-50">
                      <Code size={12} />
                    </div>
                    <span className="text-[10px] font-mono text-muted uppercase tracking-widest">
                      {parsed.type === 'details-open' ? 'Details Start' : 'Details End'}
                    </span>
                    <span className="text-xs ml-2 font-mono opacity-40">
                      {line}
                    </span>
                  </div>
                );
              } else if (parsed.type === 'summary' || parsed.type === 'comment') {
                const isComment = parsed.type === 'comment';
                return (
                  <div 
                    className={cn(
                      "flex-1 flex items-center gap-2 py-1 px-2 rounded border transition-colors focus-within:ring-1 focus-within:ring-accent",
                      isComment 
                        ? (isDark ? "bg-orange-500/10 border-orange-500/20" : "bg-orange-50 border-orange-200")
                        : (isDark ? "bg-zinc-800/20 border-border/30" : "bg-zinc-100/50 border-border/50")
                    )}
                  >
                    <div className={cn("opacity-50", isComment ? "text-orange-500" : "text-accent")}>
                      {isComment ? <Type size={12} /> : <ChevronDown size={12} />}
                    </div>
                    <span className={cn(
                      "text-[10px] font-mono uppercase tracking-widest",
                      isComment ? "text-orange-500/70" : "text-muted"
                    )}>
                      {isComment ? 'Comment' : 'Summary'}
                    </span>
                    <InlineRowEditor
                      initialContent={parsed.content}
                      isPlainText={isComment}
                      onChange={(text) => {
                        if (isComment) {
                          handleLineChange(i, `<!-- ${text} -->`);
                        } else {
                          handleLineChange(i, `<summary>${htmlToMd(text)}</summary>`);
                        }
                      }}
                      onKeyDown={(e) => handleKeyDown(e, i)}
                      onBlur={() => {}}
                      className={cn(
                        "text-xs ml-2",
                        isComment ? "font-mono text-orange-500/90" : "font-bold text-foreground"
                      )}
                    />
                    {!isComment && (
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          const newTitle = prompt('Enter section title:', parsed.content);
                          if (newTitle !== null) {
                            handleLineChange(i, `<summary>${newTitle}</summary>`);
                          }
                        }}
                        className="ml-auto p-1 hover:bg-accent/20 rounded text-accent transition-colors"
                      >
                        <Pencil size={10} />
                      </button>
                    )}
                  </div>
                );
              } else if (parsed.type === 'header') {
                const level = parsed.prefix.trim().length;
                textStyle = cn(
                  "font-bold text-foreground",
                  level === 1 && "text-3xl",
                  level === 2 && "text-2xl",
                  level === 3 && "text-xl",
                  level >= 4 && "text-lg"
                );
              } else if (parsed.type === 'summary') {
                visualMarker = <div className="mt-1 text-muted transform rotate-90 scale-75">▶</div>;
                textStyle = "font-bold text-lg text-foreground";
              }

              return (
                <>
                  {visualMarker}
                  <InlineRowEditor
                    initialContent={context.isInsideCodeBlock ? (parsed.type === 'code-fence' ? parsed.content : line) : mdToHtml(parsed.content)}
                    isPlainText={context.isInsideCodeBlock}
                    onChange={(text) => {
                      if (context.isInsideCodeBlock) {
                        if (parsed.type === 'code-fence') {
                          handleLineChange(i, '```' + text);
                        } else {
                          handleLineChange(i, text);
                        }
                      } else {
                        handleLineChange(i, parsed.prefix + htmlToMd(text) + parsed.suffix);
                      }
                    }}
                    onKeyDown={(e) => handleKeyDown(e, i)}
                    onBlur={() => {
                      setTimeout(() => {
                        if (document.activeElement?.tagName !== 'BUTTON') {
                          // setFocusedIndex(null);
                        }
                      }, 100);
                    }}
                    className={cn("min-h-[1.5rem]", textStyle)}
                  />
                </>
              );
            })()}
          </div>
        ) : (
          <div className={cn(
            "max-w-none",
            !line && "opacity-20 italic text-[10px]"
          )}>
            {(() => {
              if (parsed.type === 'comment') {
                return (
                  <div className={cn(
                    "flex items-center gap-2 py-1.5 px-3 rounded-md border text-xs font-mono mb-2",
                    isDark ? "bg-orange-500/10 border-orange-500/20 text-orange-400/80" : "bg-orange-50 border-orange-200 text-orange-600/80"
                  )}>
                    <div className="opacity-50"><Type size={12} /></div>
                    {parsed.content}
                  </div>
                );
              }
              if (parsed.type === 'summary') {
                return (
                  <div className="flex items-center gap-2 py-1 group/summary">
                    <div className="w-4 h-4 flex items-center justify-center text-muted">
                      <span className="transform rotate-90 scale-75">▶</span>
                    </div>
                    <h4 className="text-base font-bold text-foreground m-0">{parsed.content}</h4>
                  </div>
                );
              }
              if (parsed.type === 'details-open' || parsed.type === 'details-close') {
                return (
                  <div className="text-[10px] font-mono text-muted opacity-40 py-1 select-none">
                    {line}
                  </div>
                );
              }
              if (context.isInsideCodeBlock) {
                let displayLine = line;
                let colorClass = "text-foreground opacity-90";

                if (parsed.type === 'code-fence') {
                  displayLine = `\`\`\`${parsed.content}`;
                  colorClass = "text-accent font-bold opacity-50";
                } else if (isPartofBlock && lines[renderLinesStartIdx(i)]?.match(/^```json/)) {
                  // Basic JSON highlighting: keys vs values
                  const isKey = displayLine.trim().match(/^".*"\s*:/);
                  if (isKey) {
                    return (
                      <div className={cn("font-mono text-xs py-0.5 whitespace-pre", colorClass)}>
                        <span className="text-blue-400">{displayLine.split(':')[0]}</span>
                        <span className="text-foreground">:</span>
                        <span className="text-orange-300">{displayLine.split(':').slice(1).join(':')}</span>
                      </div>
                    );
                  }
                }

                return (
                  <div className={cn("font-mono text-xs py-0.5 whitespace-pre", colorClass)}>
                    {displayLine}
                  </div>
                );
              }

              let textStyle = "text-sm leading-relaxed text-foreground";
              if (parsed.type === 'header') {
                const level = parsed.prefix.trim().length;
                textStyle = cn(
                  "font-bold text-foreground",
                  level === 1 && "text-3xl",
                  level === 2 && "text-2xl",
                  level === 3 && "text-xl",
                  level >= 4 && "text-lg"
                );
              } else if (parsed.type === 'quote') {
                textStyle = "italic text-muted pl-2 border-l-2 border-accent/30";
              }

              return (
                <div className={textStyle}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeHighlight]}
                    components={{
                      p: ({ node, ...props }) => <span {...props} />,
                      h1: ({ node, ...props }) => <span {...props} />,
                      h2: ({ node, ...props }) => <span {...props} />,
                      h3: ({ node, ...props }) => <span {...props} />,
                      h4: ({ node, ...props }) => <span {...props} />,
                      h5: ({ node, ...props }) => <span {...props} />,
                      h6: ({ node, ...props }) => <span {...props} />,
                    }}
                  >
                    {line || 'Click to add text...'}
                  </ReactMarkdown>
                </div>
              );
            })()}
          </div>
        )}

        <div className="absolute -left-8 top-1 opacity-0 group-hover:opacity-40">
          <Type size={12} className="text-muted" />
        </div>
      </div>
    );
  };

  const renderLines = () => {
    const rendered = [];
    let currentCodeBlock: { lines: number[], lang: string } | null = null;

    for (let i = 0; i < lines.length; i++) {
      const context = lineContexts[i];
      const parsed = parseLine(lines[i]);

      if (context.isInsideCodeBlock) {
        if (!currentCodeBlock) {
          currentCodeBlock = { lines: [], lang: '' };
        }
        if (parsed.type === 'code-fence' && currentCodeBlock.lines.length === 0) {
          currentCodeBlock.lang = parsed.content;
        }
        currentCodeBlock.lines.push(i);

        // Check if this is the last line of the code block
        const isLastLine = i === lines.length - 1 || !lineContexts[i + 1].isInsideCodeBlock;
        if (isLastLine) {
          const blockLines = currentCodeBlock.lines;
          const lang = currentCodeBlock.lang;

          rendered.push(
            <div
              key={`code-block-${blockLines[0]}`}
              className={cn(
                "my-4 rounded-lg overflow-hidden border border-border/50",
                isDark ? "bg-zinc-900/80" : "bg-zinc-100/80",
                lang === 'json' && "border-accent/20 shadow-lg shadow-accent/5"
              )}
            >
              {lang && (
                <div className="flex items-center justify-between px-3 py-1.5 bg-black/20 border-b border-white/5">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-muted opacity-50">{lang}</span>
                  {lang === 'json' && <span className="text-[10px] text-accent/70 font-mono">Formatted JSON Block</span>}
                </div>
              )}
              <div className="p-0">
                {blockLines.map(idx => renderLine(idx, true))}
              </div>
            </div>
          );
          currentCodeBlock = null;
        }
      } else {
        rendered.push(renderLine(i, false));
      }
    }
    return rendered;
  };

  const handleCopy = () => {
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
            </div>
            <h3 className="text-sm font-bold text-foreground">{prd.title}</h3>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex bg-panel border border-border rounded-lg p-1 mr-2">
            <button
              onClick={() => {
                setIsPreview(!isPreview);
                if (!isPreview) setFocusedIndex(null);
              }}
              className={cn(
                "p-1.5 rounded transition-all flex items-center gap-2 px-3 text-[10px] font-bold uppercase tracking-wider",
                isPreview 
                  ? (isDark ? "bg-zinc-800 text-accent" : "bg-zinc-200 text-accent") 
                  : "text-muted hover:text-foreground"
              )}
              title={isPreview ? "Switch to Editor" : "Switch to Preview"}
            >
              {isPreview ? <Pencil size={14} /> : <Eye size={14} />}
              {isPreview ? "Edit" : "Preview"}
            </button>
          </div>

          {!isPreview && (
            <div className="flex bg-panel border border-border rounded-lg p-1 mr-4 animate-in fade-in zoom-in-95 duration-200">
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyFormat(focusedIndex, '**', '**')} icon={<Bold size={14} />} label="Bold (Ctrl+B)" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyFormat(focusedIndex, '_', '_')} icon={<Italic size={14} />} label="Italic (Ctrl+I)" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyFormat(focusedIndex, '~~', '~~')} icon={<Strikethrough size={14} />} label="Strikethrough" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyFormat(focusedIndex, '`', '`')} icon={<Code size={14} />} label="Inline Code" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyFormat(focusedIndex, 'link', '')} icon={<Link size={14} />} label="Link (Ctrl+K)" />
              <div className="w-px h-4 bg-border mx-1 self-center" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && toggleList(focusedIndex)} icon={<Type size={14} />} label="Toggle List (Ctrl+L)" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && toggleChecklist(focusedIndex)} icon={<ListTodo size={14} />} label="Toggle Checklist" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyFormat(focusedIndex, 'quote', '')} icon={<Quote size={14} />} label="Quote" />
              <div className="w-px h-4 bg-border mx-1 self-center" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && insertDetails(focusedIndex)} icon={<Plus size={14} />} label="Insert Details Block" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && removeDetails(focusedIndex)} icon={<Trash2 size={14} />} label="Remove Details Block" />
              <div className="w-px h-4 bg-border mx-1 self-center" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyHeader(focusedIndex, 1)} icon={<Heading1 size={14} />} label="H1 (Ctrl+1)" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyHeader(focusedIndex, 2)} icon={<Heading2 size={14} />} label="H2 (Ctrl+2)" />
              <ToolbarButton isDark={isDark} onClick={() => focusedIndex !== null && applyHeader(focusedIndex, 3)} icon={<Heading3 size={14} />} label="H3 (Ctrl+3)" />
            </div>
          )}

          <button
            onClick={handleCopy}
            className={cn(
              "p-2 rounded-lg text-muted transition-colors mr-2",
              isDark ? "hover:bg-zinc-800" : "hover:bg-zinc-200"
            )}
            title="Copy to Clipboard"
          >
            {copied ? <Check size={18} className="text-green-500" /> : <Copy size={18} />}
          </button>

          <button
            onClick={onSave}
            className="px-4 py-2 bg-accent text-white rounded-lg text-xs font-bold transition-all flex items-center gap-2 shadow-lg shadow-accent/10 hover:brightness-110"
            style={{ backgroundColor: accentColor }}
          >
            <Save size={14} />
            Save PRD
          </button>
        </div>
      </div>

      <div 
        ref={scrollContainerRef}
        className="flex-1 bg-panel border border-border rounded-xl overflow-y-auto overflow-x-hidden scrollbar-thin p-6"
        onClick={(e) => {
          if (isPreview) return;
          if (e.target === e.currentTarget) {
            setFocusedIndex(lines.length - 1);
          }
        }}
      >
        <div className="max-w-4xl mx-auto">
          {renderLines()}
        </div>
      </div>

      {contextMenu && (
        <div 
          ref={contextMenuRef}
          className={cn(
            "fixed z-[100] w-[200px] bg-panel border border-border rounded-xl shadow-[0_8px_30px_rgb(0,0,0,0.5)] p-1.5 animate-in fade-in zoom-in-95 duration-100 backdrop-blur-md",
            isDark ? "bg-zinc-900/95" : "bg-white/95"
          )}
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <div className="px-2 py-1 mb-1 text-[10px] font-bold text-muted uppercase tracking-wider opacity-50 border-b border-border/50">
            Formatting
          </div>
          <ContextMenuItem isDark={isDark} onClick={() => { applyFormat(contextMenu.index, '**', '**'); setContextMenu(null); }} icon={<Bold size={12} />} label="Bold" shortcut="Ctrl+B" />
          <ContextMenuItem isDark={isDark} onClick={() => { applyFormat(contextMenu.index, '_', '_'); setContextMenu(null); }} icon={<Italic size={12} />} label="Italic" shortcut="Ctrl+I" />
          <ContextMenuItem isDark={isDark} onClick={() => { applyFormat(contextMenu.index, '~~', '~~'); setContextMenu(null); }} icon={<Strikethrough size={12} />} label="Strikethrough" />
          <ContextMenuItem isDark={isDark} onClick={() => { applyFormat(contextMenu.index, 'link', ''); setContextMenu(null); }} icon={<Link size={12} />} label="Link" shortcut="Ctrl+K" />
          
          <div className="h-px bg-border/50 my-1.5 mx-1" />
          <div className="px-2 py-1 mb-1 text-[10px] font-bold text-muted uppercase tracking-wider opacity-50">
            Structure
          </div>
          <ContextMenuItem isDark={isDark} onClick={() => { toggleList(contextMenu.index); setContextMenu(null); }} icon={<Type size={12} />} label="List" shortcut="Ctrl+L" />
          <ContextMenuItem isDark={isDark} onClick={() => { toggleChecklist(contextMenu.index); setContextMenu(null); }} icon={<ListTodo size={12} />} label="Checklist" />
          <ContextMenuItem isDark={isDark} onClick={() => { applyFormat(contextMenu.index, 'quote', ''); setContextMenu(null); }} icon={<Quote size={12} />} label="Quote" />
          <ContextMenuItem isDark={isDark} onClick={() => { insertDetails(contextMenu.index); setContextMenu(null); }} icon={<Plus size={12} />} label="Insert Details" />
          <ContextMenuItem isDark={isDark} onClick={() => { removeDetails(contextMenu.index); setContextMenu(null); }} icon={<Trash2 size={12} />} label="Remove Details" />
          
          <div className="h-px bg-border/50 my-1.5 mx-1" />
          <div className="px-2 py-1 mb-1 text-[10px] font-bold text-muted uppercase tracking-wider opacity-50">
            Headings
          </div>
          <ContextMenuItem isDark={isDark} onClick={() => { applyHeader(contextMenu.index, 1); setContextMenu(null); }} icon={<Heading1 size={12} />} label="Header 1" shortcut="Ctrl+1" />
          <ContextMenuItem isDark={isDark} onClick={() => { applyHeader(contextMenu.index, 2); setContextMenu(null); }} icon={<Heading2 size={12} />} label="Header 2" shortcut="Ctrl+2" />
          <ContextMenuItem isDark={isDark} onClick={() => { applyHeader(contextMenu.index, 3); setContextMenu(null); }} icon={<Heading3 size={12} />} label="Header 3" shortcut="Ctrl+3" />
        </div>
      )}
    </div>
  );
};

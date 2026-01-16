import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const Accordion = ({ 
  title, 
  children, 
  defaultOpen = true,
  icon: Icon,
  isDark = true
}: { 
  title: string, 
  children: React.ReactNode, 
  defaultOpen?: boolean,
  icon?: any,
  isDark?: boolean
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-zinc-800/50 last:border-0">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-full flex items-center justify-between px-4 py-3 transition-colors group",
          isDark ? "hover:bg-zinc-800/30" : "hover:bg-zinc-200/30"
        )}
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon size={14} className={cn("text-muted group-hover:text-foreground", isOpen && "text-foreground")} />}
          <span className={cn("text-[10px] font-bold uppercase tracking-widest transition-colors", 
            isOpen ? "text-foreground" : "text-muted group-hover:text-foreground"
          )}>
            {title}
          </span>
        </div>
        <ChevronDown size={14} className={cn("text-muted transition-transform duration-200", isOpen && "rotate-180")} />
      </button>
      {isOpen && (
        <div className="px-2 pb-4">
          {children}
        </div>
      )}
    </div>
  );
};

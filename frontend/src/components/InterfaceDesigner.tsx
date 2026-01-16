import React from 'react';
import { Layout } from 'lucide-react';

export const InterfaceDesigner: React.FC<{ accentColor: string; isDark: boolean }> = ({ accentColor, isDark }) => {
  return (
    <div className="flex flex-col h-full w-full bg-background overflow-hidden">
      <div className="flex items-center justify-between p-6 border-b border-border">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Layout size={32} style={{ color: accentColor }} />
            Interface Designer
          </h1>
          <p className="text-muted mt-2">Design and prototype your user interfaces</p>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="text-center space-y-4">
          <div className="w-24 h-24 rounded-2xl bg-panel border border-border flex items-center justify-center mx-auto opacity-20">
            <Layout size={48} />
          </div>
          <h2 className="text-xl font-medium text-muted">Interface Designer Canvas</h2>
          <p className="text-sm text-muted/60 max-w-md mx-auto">
            This is the future home of the Interface Designer. Here you will be able to drag and drop components, manage layouts, and export code.
          </p>
        </div>
      </div>
    </div>
  );
};

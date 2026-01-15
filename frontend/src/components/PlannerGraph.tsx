import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background, 
  MarkerType,
  ConnectionMode,
  useNodesState,
  useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import { invoke } from '@tauri-apps/api/tauri';
import yaml from 'js-yaml';
import { PRD } from './PlannerBoard';

const COLUMNS = [
  { id: 'inbox', folder: 'product/inbox', color: '#71717a' },
  { id: 'backlog', folder: 'product/backlog', color: '#94a3b8' },
  { id: 'next', folder: 'product/next', color: '#60a5fa' },
  { id: 'in_progress', folder: 'product/in_progress', color: '#4ade80' },
  { id: 'archive', folder: 'product/history', color: '#a855f7' },
];

const PRDNode = ({ data }: { data: any }) => {
  return (
    <div 
      className="px-4 py-3 rounded-lg border-2 bg-zinc-900 text-white min-w-[180px] shadow-xl"
      style={{ borderColor: data.color }}
    >
      <div className="text-[10px] font-mono font-bold text-zinc-500 mb-1">{data.id}</div>
      <div className="text-sm font-bold truncate">{data.title}</div>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded bg-zinc-800" style={{ color: data.color }}>
          {data.columnId}
        </span>
        {data.owner && (
           <span className="text-[9px] text-zinc-500 truncate max-w-[80px]">@{data.owner}</span>
        )}
      </div>
    </div>
  );
};

const nodeTypes = {
  prd: PRDNode,
};

export const PlannerGraph = ({ 
  workspaceRoot,
  onSelectPRD
}: { 
  workspaceRoot: string;
  onSelectPRD: (id: string) => void;
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const loadData = useCallback(async () => {
    if (!workspaceRoot) return;
    try {
      const prds: any[] = [];
      for (const col of COLUMNS) {
        const path = `${workspaceRoot}/${col.folder}`;
        try {
          const entries = await invoke<any[]>('list_directory', { path });
          for (const entry of entries) {
            if (!entry.is_dir && entry.name.endsWith('.md')) {
              const content = await invoke<string>('read_file_content', { path: entry.path });
              const match = content.match(/```yaml\n([\s\S]*?)\n```/);
              let meta: any = {};
              if (match) {
                try {
                  meta = yaml.load(match[1]);
                } catch (e) {}
              }
              
              prds.push({
                id: meta.id || entry.name.replace('.md', ''),
                title: meta.title || entry.name,
                columnId: col.id,
                color: col.color,
                depends_on: meta.depends_on || [],
                owner: meta.agent || meta.owner,
                path: entry.path
              });
            }
          }
        } catch (e) {}
      }

      // Create nodes
      const newNodes: Node[] = prds.map((prd, index) => {
        // Simple layout: column-based X, index-based Y
        const colIndex = COLUMNS.findIndex(c => c.id === prd.columnId);
        const colPrds = prds.filter(p => p.columnId === prd.columnId);
        const inColIndex = colPrds.findIndex(p => p.id === prd.id);
        
        return {
          id: prd.id,
          type: 'prd',
          position: { x: colIndex * 300, y: inColIndex * 120 },
          data: { ...prd },
        };
      });

      // Create edges
      const newEdges: Edge[] = [];
      prds.forEach(prd => {
        if (prd.depends_on) {
          prd.depends_on.forEach((depId: string) => {
            // Only add edge if dependency exists
            if (prds.find(p => p.id === depId)) {
              newEdges.push({
                id: `e-${depId}-${prd.id}`,
                source: depId,
                target: prd.id,
                animated: prd.columnId === 'in_progress',
                style: { stroke: prd.color, strokeWidth: 2 },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: prd.color,
                },
              });
            }
          });
        }
      });

      setNodes(newNodes);
      setEdges(newEdges);
    } catch (err) {
      console.error('Failed to load graph data:', err);
    }
  }, [workspaceRoot]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="h-full w-full bg-zinc-950/50 rounded-xl border border-zinc-800/50 overflow-hidden relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelectPRD(node.id)}
        connectionMode={ConnectionMode.Loose}
        fitView
      >
        <Background color="#27272a" gap={20} />
        <Controls className="bg-zinc-900 border-zinc-800 fill-zinc-400" />
      </ReactFlow>
      
      <div className="absolute top-4 right-4 flex flex-col gap-2 p-3 bg-zinc-900/80 border border-zinc-800 rounded-lg backdrop-blur-sm z-10">
        <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-1">Legend</div>
        {COLUMNS.map(col => (
          <div key={col.id} className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: col.color }} />
            <span className="text-[10px] text-zinc-400 capitalize">{col.id}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

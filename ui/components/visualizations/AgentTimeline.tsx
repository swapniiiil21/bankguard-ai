'use client';

import React, { useMemo } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  MarkerType,
  Handle,
  Position
} from 'reactflow';
import 'reactflow/dist/style.css';

// Custom Node for displaying Agent states with animated borders
const AgentNode = ({ data }: any) => {
  const statusColor = data.status === 'processing' ? 'border-blue-500 animate-pulse' :
                      data.status === 'success' ? 'border-green-500' :
                      data.status === 'failed' ? 'border-red-500' : 'border-slate-700';

  return (
    <div className={`px-4 py-2 shadow-lg rounded-md bg-slate-900 border-2 ${statusColor}`}>
      <Handle type="target" position={Position.Top} className="w-16 !bg-teal-500" />
      <div className="flex flex-col">
        <div className="text-sm font-bold text-white">{data.label}</div>
        <div className="text-xs text-slate-400">{data.detail}</div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-16 !bg-teal-500" />
    </div>
  );
};

const nodeTypes = { agent: AgentNode };

export default function AgentTimeline({ executionTrace }: { executionTrace: any }) {
  // Translate LangGraph trace into React Flow nodes
  const nodes = useMemo(() => [
    { id: '1', type: 'agent', position: { x: 250, y: 0 }, data: { label: 'Supervisor', detail: 'Received Event', status: 'success' } },
    { id: '2', type: 'agent', position: { x: 100, y: 100 }, data: { label: 'KYC Agent', detail: 'Validating Doc', status: 'success' } },
    { id: '3', type: 'agent', position: { x: 400, y: 100 }, data: { label: 'Risk Intelligence', detail: 'Querying Graph', status: 'processing' } },
    { id: '4', type: 'agent', position: { x: 250, y: 250 }, data: { label: 'Reflection', detail: 'Waiting...', status: 'idle' } },
  ], [executionTrace]);

  const edges = useMemo(() => [
    { id: 'e1-2', source: '1', target: '2', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e1-3', source: '1', target: '3', animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e2-4', source: '2', target: '4', markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e3-4', source: '3', target: '4', markerEnd: { type: MarkerType.ArrowClosed } },
  ], []);

  return (
    <div className="w-full h-full bg-slate-950 rounded-xl overflow-hidden border border-slate-800">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView>
        <Background color="#334155" gap={16} />
        <Controls className="fill-slate-400" />
      </ReactFlow>
    </div>
  );
}

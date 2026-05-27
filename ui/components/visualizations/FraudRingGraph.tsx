'use client';

import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';

export default function FraudRingGraph({ elements }: { elements: any }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const layoutRef = useRef<cytoscape.Layouts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize Cytoscape ONCE
    cyRef.current = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#3b82f6',
            'label': 'data(id)',
            'color': '#fff',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'font-size': '12px'
          }
        },
        {
          selector: 'node[type="Device"]',
          style: {
            'background-color': '#ef4444', 
            'shape': 'triangle'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '10px',
            'color': '#94a3b8',
            'text-rotation': 'autorotate'
          }
        }
      ]
    });

    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      console.log('Tapped node: ', node.id());
    });

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, []); // Empty dependency array ensures cy is only created/destroyed on mount/unmount

  // Handle data updates separately
  useEffect(() => {
    if (cyRef.current && elements) {
      cyRef.current.elements().remove();
      cyRef.current.add(elements);
      
      const layout = cyRef.current.layout({
        name: 'cose', 
        padding: 30,
        animate: false // <--- THIS FIXES THE NOTIFY ERROR IN STRICT MODE
      });
      layout.run();
      
      return () => {
        layout.stop();
      };
    }
  }, [elements]);

  return (
    <div className="w-full h-full bg-slate-950 rounded-xl border border-slate-800">
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}

'use client';

import React, { useState } from 'react';
import AgentTimeline from '../../../components/visualizations/AgentTimeline';
import FraudRingGraph from '../../../components/visualizations/FraudRingGraph';
import { useWebsocket, useAlertStore } from '../../../hooks/useWebsocket';
import { Terminal, ShieldAlert, Cpu } from 'lucide-react';

export default function InvestigationCockpit() {
  // Connect to the streaming gateway
  useWebsocket('ws://localhost:8000/api/v1/ws/alerts');
  const alerts = useAlertStore((state) => state.alerts);
  const graphData = useAlertStore((state) => state.graphData);
  const timelineTrace = useAlertStore((state) => state.timelineTrace);
  const uploadedDocuments = useAlertStore((state) => state.uploadedDocuments);

  const [inputValue, setInputValue] = useState('');
  const [chatMessages, setChatMessages] = useState([
    { role: 'copilot', text: 'I noticed that Account A and Account B are using the exact same iPhone device fingerprint. Would you like me to run a deep scan on their transaction history?' }
  ]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;
    
    const userMsg = inputValue;
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setInputValue('');

    try {
      const response = await fetch('http://localhost:8000/api/v1/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, documents: uploadedDocuments }),
      });
      
      if (!response.ok) throw new Error("Failed to get response");
      
      const data = await response.json();
      setChatMessages(prev => [...prev, { role: 'copilot', text: data.response }]);
    } catch (error) {
      setChatMessages(prev => [...prev, { role: 'copilot', text: "Sorry, I am currently unable to reach the AI models. Please ensure the backend is running and API keys are set." }]);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 font-sans p-4 gap-4">
      {/* LEFT PANE: Evidence & Queue */}
      <div className="w-1/4 flex flex-col gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex-grow flex flex-col">
          <h2 className="text-xl font-bold flex items-center gap-2 mb-4">
            <ShieldAlert className="text-red-500" /> Live Alert Queue
          </h2>
          <div className="flex-grow overflow-y-auto space-y-3">
            {alerts.length === 0 ? (
              <p className="text-slate-500 text-sm">Waiting for incoming Kafka events...</p>
            ) : (
              alerts.map((alert, i) => (
                <div key={i} className="p-3 bg-slate-800 rounded-lg border-l-4 border-red-500 shadow-md">
                  <p className="font-mono text-xs text-slate-400">TXN: {alert.transaction_id}</p>
                  <p className="font-semibold mt-1">Score: {alert.fraud_score}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* CENTER PANE: LangGraph Agent Timeline */}
      <div className="w-2/4 flex flex-col gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 h-[40%] flex flex-col">
          <h2 className="text-xl font-bold flex items-center gap-2 mb-4">
            <Cpu className="text-blue-500" /> AI Execution Timeline
          </h2>
          <div className="flex-grow">
            <AgentTimeline executionTrace={timelineTrace} />
          </div>
        </div>

        {/* BOTTOM CENTER: Neo4j Fraud Intelligence */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 h-[60%] flex flex-col">
          <h2 className="text-xl font-bold mb-4">Graph Intelligence (Neo4j)</h2>
          <div className="flex-grow">
            <FraudRingGraph elements={graphData} />
          </div>
        </div>
      </div>

      {/* RIGHT PANE: AI Copilot */}
      <div className="w-1/4 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col">
        <h2 className="text-xl font-bold flex items-center gap-2 mb-4">
          <Terminal className="text-emerald-500" /> Investigation Copilot
        </h2>
        <div className="flex-grow bg-slate-950 rounded-lg p-4 border border-slate-800 flex flex-col min-h-0">
          <div className="flex-grow overflow-y-auto space-y-4 pr-2">
            {chatMessages.map((msg, idx) => (
              <div key={idx} className={`p-3 rounded-lg text-sm ${msg.role === 'copilot' ? 'bg-slate-800 border border-slate-700' : 'bg-blue-900/40 border border-blue-800/50'}`}>
                {msg.role === 'copilot' ? (
                  <span className="font-bold text-emerald-400">Copilot: </span>
                ) : (
                  <span className="font-bold text-blue-400">You: </span>
                )}
                {msg.text}
              </div>
            ))}
          </div>
          <div className="mt-4 flex-shrink-0">
            <input 
              type="text" 
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendMessage();
              }}
              placeholder="Ask the AI investigator... (Press Enter)" 
              className="w-full bg-slate-800 text-sm text-white px-4 py-2 rounded-md border border-slate-700 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

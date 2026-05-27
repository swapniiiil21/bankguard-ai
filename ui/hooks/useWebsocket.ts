import { useEffect, useRef } from 'react';
import { create } from 'zustand';

// Zustand store to manage real-time alerts globally across the UI
interface AlertState {
  alerts: any[];
  addAlert: (alert: any) => void;
  clearAlerts: () => void;
  timelineTrace: any[];
  setTimelineTrace: (trace: any[]) => void;
  graphData: any[];
  setGraphData: (data: any[]) => void;
  uploadedDocuments: string[];
  setUploadedDocuments: (docs: string[]) => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  addAlert: (alert) => set((state) => ({ alerts: [alert, ...state.alerts] })),
  clearAlerts: () => set({ alerts: [] }),
  timelineTrace: [],
  setTimelineTrace: (trace) => set({ timelineTrace: trace }),
  uploadedDocuments: [],
  setUploadedDocuments: (docs) => set({ uploadedDocuments: docs }),
  graphData: [
    { data: { id: 'ACC_123', label: 'User A' } },
    { data: { id: 'ACC_456', label: 'User B' } },
    { data: { id: 'DEV_XY99', label: 'Shared iPhone', type: 'Device' } },
    { data: { source: 'ACC_123', target: 'DEV_XY99', label: 'USED_DEVICE' } },
    { data: { source: 'ACC_456', target: 'DEV_XY99', label: 'USED_DEVICE' } },
  ], // Default placeholder graph
  setGraphData: (data) => set({ graphData: data }),
}));

export const useWebsocket = (url: string) => {
  const ws = useRef<WebSocket | null>(null);
  const addAlert = useAlertStore((state) => state.addAlert);

  useEffect(() => {
    // Connect to the FastAPI WebSocket endpoint which streams Kafka events
    ws.current = new WebSocket(url);

    ws.current.onopen = () => console.log(`WebSocket Connected: ${url}`);
    
    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'HIGH_RISK_ALERT') {
          addAlert(data.payload);
          // In a real app, integrate toast notification library here (e.g. sonner)
          console.warn('FRAUD ALERT:', data.payload);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message', err);
      }
    };

    ws.current.onerror = (error) => console.error('WebSocket Error:', error);
    ws.current.onclose = () => console.log('WebSocket Disconnected');

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [url, addAlert]);

  return ws.current;
};

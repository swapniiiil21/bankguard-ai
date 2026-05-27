#!/bin/bash
# start.sh — Launch FastAPI and Streamlit concurrently

set -e

echo "Starting BankGuard AI services..."

# Start FastAPI in the background
python -m uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info &

API_PID=$!
echo "FastAPI started (PID: $API_PID)"

# Wait for API to be ready
echo "Waiting for API to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "API is ready!"
        break
    fi
    sleep 2
done

# Start Streamlit
streamlit run ui/app.py \
    --server.port 7860 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.fileWatcherType none \
    --browser.gatherUsageStats false &

UI_PID=$!
echo "Streamlit started (PID: $UI_PID)"

# Wait for either process to exit
wait $API_PID $UI_PID
echo "A service exited. Shutting down..."
kill $API_PID $UI_PID 2>/dev/null || true

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Run the Streamlit application
streamlit run app.py

# Install dependencies
pip install -r requirements.txt

# Run in virtual environment (recommended)
source .venv/bin/activate
streamlit run app.py
```

## Architecture Overview

This is a single-file Streamlit application (`app.py`) that performs tail risk analysis for flight delays and cancellations. The application consists of three main sections:

### 1. Data Input Layer
- **FlightAware API Integration**: Fetches real-time flight history using the FlightAware AeroAPI
- **CSV Upload Processing**: Parses user-uploaded flight data with automatic date/time parsing and overnight flight handling
- Both data sources are normalized to a common format for analysis

### 2. Analysis Engine
- **Smart Filtering**: Filters historical flights within a 3-hour window of the user's scheduled time
- **Delay Calculation**: Computes delay minutes with 24-hour wrap handling for overnight flights
- **Risk Categorization**: Classifies flights into risk categories (On Time, Nuisance, Significant, Missed Deadline)
- **Statistical Metrics**: Calculates cancellation rates, average delays, and deadline miss probabilities

### 3. Visualization Layer
- **Interactive Dashboard**: Sidebar configuration with schedule and deadline inputs
- **Risk Metrics Display**: Real-time metrics with color-coded alerts
- **Delay Distribution Chart**: Plotly histogram showing delay patterns with deadline overlay

## Key Technical Details

### Data Processing Pipeline
The application handles two data sources with different schemas:
- CSV data uses `actual_in` timestamps for filtering and delay calculation
- API data uses `sched_in_local` with timezone conversion and UTC handling
- Both sources undergo standardization in the analysis engine

### Configuration Requirements
- FlightAware API key must be stored in `st.secrets["FLIGHTAWARE_API_KEY"]`
- Streamlit secrets configuration required for API functionality

### Time Handling
- Supports overnight flights with automatic date adjustment
- Smart filtering uses circular time distance calculation (handles day boundaries)
- Timezone-aware processing for API data with local time conversion

## MCP Server

### Simple Structure
```
app.py                   # Streamlit application
server.py               # MCP server (uses functions from app.py)
test_simple_server.py   # Test the server functions
requirements.txt        # Dependencies
```

### Running the MCP Server
```bash
# Install dependencies
pip install -r requirements.txt

# Run the MCP server
python server.py
```

### MCP Configuration
Add to your Claude Desktop config:
```json
"tail-risk-analyzer": {
  "command": "/path/to/your/.venv/bin/python",
  "args": ["/path/to/Tail-Risk-App-Streamlit/server.py"]
}
```

### Available MCP Tool
- `analyze_csv_flight_data`: Complete tail risk analysis from CSV data using proven algorithms from the Streamlit app

### Features
- Smart time-based filtering (3-hour window)
- Overnight flight handling  
- Risk categorization and deadline analysis
- Comprehensive statistical metrics
- Uses the exact working code from app.py
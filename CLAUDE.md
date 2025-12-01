# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the Streamlit application
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
# Create and activate virtual environment (if not done already)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the MCP server
python server.py
```

### MCP Configuration for Claude Desktop

**Step 1: Locate your Claude Desktop config file**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Step 2: Add the tail-risk-analyzer server to your config**
```json
{
  "mcpServers": {
    "tail-risk-analyzer": {
      "command": "/path/to/your/.venv/bin/python",
      "args": ["/path/to/Tail-Risk-App-Streamlit/server.py"]
    }
  }
}
```

**Step 3: Update the paths to match your setup**
Replace `/path/to/your/.venv/bin/python` with your actual virtual environment path.
Replace `/path/to/Tail-Risk-App-Streamlit/server.py` with your actual project path.

**Example with real paths:**
```json
{
  "mcpServers": {
    "tail-risk-analyzer": {
      "command": "/Users/username/Documents/dev/Tail-Risk-App-Streamlit/.venv/bin/python",
      "args": ["/Users/username/Documents/dev/Tail-Risk-App-Streamlit/server.py"]
    }
  }
}
```

**Step 4: Restart Claude Desktop**
Close and reopen Claude Desktop for the changes to take effect.

### Available MCP Tool
- `analyze_csv_flight_data`: Complete tail risk analysis from CSV data using proven algorithms from the Streamlit app

### Features
- Smart time-based filtering (3-hour window)
- Overnight flight handling  
- Risk categorization and deadline analysis
- Comprehensive statistical metrics
- Uses the exact working code from app.py

## Testing with Claude/Sonnet

### Step 1: Verify Setup
After restarting Claude Desktop, the tool should be available. You can verify by asking Claude:
*"What tools do you have access to?"*

You should see `analyze_csv_flight_data` in the list.

### Step 2: Test with Sample Data
Ask Claude to analyze flight data using this sample:

**Prompt:** *"Use the analyze_csv_flight_data tool to analyze this flight data for a 08:30 scheduled arrival with a 09:00 deadline:"*

**Sample CSV Data:**
```csv
Date,Aircraft,Origin,Destination,Departure,Arrival,Duration
21-Nov-25,A320,BCN,CDG,07:17AM,08:34AM,1h 17m
20-Nov-25,A20N,BCN,CDG,06:56AM,08:08AM,1h 12m
19-Nov-25,A320,BCN,CDG,07:15AM,08:45AM,1h 30m
18-Nov-25,A320,BCN,CDG,07:20AM,Cancelled,Cancelled
17-Nov-25,A20N,BCN,CDG,07:25AM,08:30AM,1h 05m
```

**Parameters:**
- `scheduled_time`: "08:30"
- `deadline_time`: "09:00"

### Step 3: Expected Results
The analysis should return:
- **Route**: BCN → CDG
- **Flights Analyzed**: 5 total, with smart filtering applied
- **Cancellation Rate**: 20% (1 cancelled flight)
- **Risk Assessment**: Based on delay distribution and deadline buffer
- **Miss Probability**: Calculated based on historical delays and cancellations

### Troubleshooting
If the tool isn't working:
1. Check the Claude Desktop logs for connection errors
2. Verify your config file paths are correct
3. Make sure the virtual environment has all dependencies installed
4. Test the server locally with `python test_simple_server.py`
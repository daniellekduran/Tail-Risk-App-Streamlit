# Tail Risk Analyzer 📉

A probabilistic flight delay and cancellation risk analysis tool with both Streamlit UI and Claude AI integration via MCP (Model Context Protocol).

## ⚠️ DISCLAIMER: PROBABILISTIC MODEL (NOT A GUARANTEE)

**Tail Risk** is a statistical tool designed for personal planning and portfolio showcase. The flight delay and cancellation predictions are based on historical data and probabilistic modeling.

**DO NOT** rely on this application for mission-critical travel decisions. The information provided is **"AS IS"** and we are not liable for missed flights, missed connections, or any subsequent damages resulting from reliance on the predictive outputs. Always consult official airline information.

## Features

- **Smart Time Filtering**: 3-hour window filtering for relevant historical flights
- **Overnight Flight Handling**: Automatic handling of flights that cross midnight
- **Risk Categorization**: On-time, nuisance delays, significant delays, missed deadlines
- **Deadline Miss Probability**: Statistical analysis of meeting hard deadlines
- **Multiple Data Sources**: CSV upload or FlightAware API integration
- **Claude AI Integration**: MCP server for AI-assisted analysis

## Data Sources & Options

### CSV Data (Recommended for Deep Analysis)
**Best for:** Historical analysis with 3+ months of data for statistical significance

**How to get CSV data:**
1. **FlightRadar24**: Search your route, export historical data
2. **FlightAware**: Manual data collection from flight history pages
3. **Airline websites**: Some provide historical performance data
4. **Airport websites**: Delay statistics and historical data

**Required CSV columns:**
- `Date` (format: DD-MMM-YY, e.g., "21-Nov-25")
- `Departure` (format: HH:MMAM/PM, e.g., "07:17AM")
- `Arrival` (format: HH:MMAM/PM, e.g., "08:34AM")

**Optional CSV columns:**
- `Origin` - Airport code (e.g., "BCN")
- `Destination` - Airport code (e.g., "CDG") 
- `Aircraft` - Aircraft type (e.g., "A320")
- `Duration` - Flight duration (used to detect cancellations if contains "Cancelled")

**Pros:**
- ✅ Deep historical data (months/years)
- ✅ Higher statistical confidence
- ✅ Free (no API costs)
- ✅ Works offline
- ✅ Complete control over data quality

**Cons:**
- ❌ Manual data collection required
- ❌ Data may become outdated
- ❌ Time-consuming to gather

### FlightAware API (Quick Analysis)
**Best for:** Quick analysis of recent flight performance (last few weeks)

**How to use FlightAware API:**
1. Sign up at [flightaware.com](https://flightaware.com/commercial/aeroapi/)
2. Get your API key (free tier available)
3. Add API key to Streamlit secrets: `st.secrets["FLIGHTAWARE_API_KEY"]`
4. Enter flight number (e.g., "VY6612") in the app
**What you get:**
- Recent flight history (typically last 2-4 weeks)
- Real-time delay data
- Cancellation information
- Automatic timezone handling
- Aircraft types and route information

**Pros:**
- ✅ Real-time, up-to-date data
- ✅ Automatic data collection
- ✅ Timezone-aware
- ✅ No manual work required
- ✅ Always current

**Cons:**
- ❌ Limited historical depth (weeks, not months)
- ❌ API costs for heavy usage
- ❌ Requires internet connection
- ❌ Less statistical significance with limited data

### Which Should You Use?

**Use CSV when:**
- You want the most accurate risk assessment
- You have time to collect 3+ months of historical data
- You're analyzing a route you fly frequently
- Statistical significance is important
- You want to track trends over time

**Use FlightAware API when:**
- You need a quick risk assessment
- You're analyzing a new or infrequent route
- You want current/recent performance data
- You don't have time to collect historical data
- You need timezone-accurate analysis

**Best Practice: Combine Both**
- Use FlightAware API for initial quick assessment
- Collect CSV data over time for routes you fly regularly
- Compare API vs CSV results to validate your analysis

### Automated Data Collection (New!)

The MCP server now includes **automated data collection tools** that Sonnet can use to gather CSV data for you:

**Available Collection Tools:**
- `collect_flightaware_csv` - Automatically collect real FlightAware data and format as CSV
- `generate_sample_csv` - Generate realistic sample data for testing and demonstrations

**How Sonnet Can Help:**
1. **"Collect data for flight VY6612"** - Sonnet will use your FlightAware API key to automatically gather historical data and format it as CSV for analysis
2. **"Generate sample data for JFK-LAX route"** - Sonnet will create realistic sample data with proper delay patterns and cancellations
3. **"Collect and analyze"** - Sonnet can combine data collection + analysis in one step

## Quick Start

### Prerequisites
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Streamlit Web App
```bash
# Activate virtual environment first (see Prerequisites)
source .venv/bin/activate

# Run the web application
streamlit run app.py
```

### Claude AI Integration
```bash
# Activate virtual environment first (see Prerequisites)
source .venv/bin/activate

# Run the MCP server
python server.py
```

## Setup for Claude Desktop

### Step 1: Configure Claude Desktop
Add to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

Replace paths with your actual installation paths.

### Step 2: Restart Claude Desktop
Close and reopen Claude Desktop for changes to take effect.

### Step 3: Test the Integration

**Option A - Test with Sample Data:**
Ask Claude: *"Use the analyze_csv_flight_data tool to analyze this flight data for a 08:30 scheduled arrival with a 09:00 deadline:"*

**Sample CSV Data:**
```csv
Date,Aircraft,Origin,Destination,Departure,Arrival,Duration
21-Nov-25,A320,BCN,CDG,07:17AM,08:34AM,1h 17m
20-Nov-25,A20N,BCN,CDG,06:56AM,08:08AM,1h 12m
19-Nov-25,A320,BCN,CDG,07:15AM,08:45AM,1h 30m
18-Nov-25,A320,BCN,CDG,07:20AM,Cancelled,Cancelled
17-Nov-25,A20N,BCN,CDG,07:25AM,08:30AM,1h 05m
```

**Option B - Test Automated Data Collection:**
Ask Claude: *"Generate sample flight data for BCN-CDG route and analyze it for an 08:30 scheduled arrival with 09:00 deadline"*

**Option C - Test Real Data Collection (requires FlightAware API key):**
Ask Claude: *"Collect flight data for VY6612 using my FlightAware API key [YOUR-KEY] and analyze for 08:30 arrival with 09:00 deadline"*

## Architecture

- **app.py**: Streamlit web application with interactive dashboard
- **server.py**: MCP server using the same proven analysis algorithms
- **test_simple_server.py**: Test suite for server functions
- **requirements.txt**: Python dependencies

## Analysis Methodology

The tool performs sophisticated tail risk analysis by:

1. **Data Processing**: Parses flight data with automatic date/time handling
2. **Smart Filtering**: Uses 3-hour time windows to find relevant historical flights
3. **Delay Calculation**: Computes delays with 24-hour wrap handling for overnight flights
4. **Statistical Analysis**: Calculates cancellation rates, delay distributions, and deadline probabilities
5. **Risk Assessment**: Flags high-risk scenarios based on probability thresholds

This approach goes beyond simple averages to identify the "tail risks" - low probability but high impact events like cancellations and significant delays.
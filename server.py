#!/usr/bin/env python3
"""
Tail Risk Analysis MCP Server

Simple MCP server using the proven functions from app.py
"""

import asyncio
import json
import sys
from typing import Any, Dict, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from io import StringIO
import requests
from urllib.parse import urljoin

from mcp.server import Server
import mcp.server.stdio
import mcp.types as types

# --- WORKING FUNCTIONS FROM APP.PY ---

def process_csv_data(csv_content: str):
    """Process CSV flight data - copied directly from app.py"""
    try:
        df = pd.read_csv(StringIO(csv_content))
        
        # Helper: Clean weird characters from scraping
        def clean(x): 
            return str(x).replace('CET', '').replace('CEST', '').strip() if pd.notnull(x) else x
        
        # 1. Parse Dates
        df['Date_dt'] = pd.to_datetime(df['Date'], format='%d-%b-%y', errors='coerce')
        
        # Drop rows where Date failed to parse
        df = df.dropna(subset=['Date_dt'])
        
        # 2. Parse Times (Departure/Arrival)
        def parse_time(row, col):
            try:
                t_str = clean(row[col])
                dt_str = f"{row['Date_dt'].strftime('%Y-%m-%d')} {t_str}"
                return pd.to_datetime(dt_str, format='%Y-%m-%d %I:%M%p')
            except:
                return pd.NaT

        df['actual_out'] = df.apply(lambda r: parse_time(r, 'Departure'), axis=1)
        df['actual_in'] = df.apply(lambda r: parse_time(r, 'Arrival'), axis=1)

        # 3. Handle Cancellations
        if 'Duration' in df.columns:
            df['is_cancelled'] = df['Duration'].astype(str).str.contains('Cancelled', case=False)
        else:
            df['is_cancelled'] = False

        # 4. Handle Overnight (Arrival < Departure)
        mask_valid = pd.notnull(df['actual_in']) & pd.notnull(df['actual_out'])
        mask_overnight = (df.loc[mask_valid, 'actual_in'].dt.time < df.loc[mask_valid, 'actual_out'].dt.time)
        df.loc[mask_valid & mask_overnight, 'actual_in'] += timedelta(days=1)

        # 5. Metadata Extraction
        meta = {
            "origin": df['Origin'].mode()[0] if 'Origin' in df.columns else "?",
            "dest": df['Destination'].mode()[0] if 'Destination' in df.columns else "?",
            "aircraft": df['Aircraft'].mode()[0] if 'Aircraft' in df.columns else "Unknown",
            "count": len(df)
        }
        df['source_type'] = 'csv'
        return df, meta

    except Exception as e:
        return None, f"Error processing CSV: {str(e)}"

def analyze_tail_risk(df: pd.DataFrame, sched_time: str, deadline_time: str = None):
    """Perform tail risk analysis - copied and adapted from app.py"""
    try:
        # Parse schedule time
        sched_arr = datetime.strptime(sched_time, "%H:%M").time()
        
        # 1. STANDARDIZE DELAY METRICS FOR CSV DATA
        if df['source_type'].iloc[0] == 'csv':
            def combine_sched(r):
                if pd.isna(r['Date_dt']): 
                    return pd.NaT
                try:
                    return datetime.combine(r['Date_dt'].date(), sched_arr)
                except:
                    return pd.NaT

            user_sched_series = df.apply(combine_sched, axis=1)
            df['user_sched_dt'] = pd.to_datetime(user_sched_series, errors='coerce')
            df = df.dropna(subset=['user_sched_dt'])
            
            df['delay_minutes'] = (df['actual_in'] - df['user_sched_dt']).dt.total_seconds() / 60
            
            # Fix 24h wrap
            df.loc[df['delay_minutes'] < -720, 'delay_minutes'] += 1440
            df.loc[df['delay_minutes'] > 720, 'delay_minutes'] -= 1440
            
            # FIX FOR SMART FILTER: Use Actual Arrival Time as the filter base
            df['sched_in_local'] = df['actual_in']
        
        # 2. INTELLIGENT FILTERING
        user_mins = sched_arr.hour * 60 + sched_arr.minute
        
        def is_relevant_time(row_sched_dt):
            if pd.isna(row_sched_dt): 
                return True 
            row_mins = row_sched_dt.hour * 60 + row_sched_dt.minute
            diff = abs(row_mins - user_mins)
            if diff > 720: 
                diff = 1440 - diff
            return diff <= 180  # 3 Hour Window

        df['is_relevant'] = df['sched_in_local'].apply(is_relevant_time)
        relevant_df = df[df['is_relevant']].copy()
        hidden_count = len(df) - len(relevant_df)
        
        # 3. METRICS
        cancel_count = relevant_df['is_cancelled'].sum()
        total_relevant = len(relevant_df)
        cancel_rate = cancel_count / total_relevant if total_relevant > 0 else 0
        
        valid_df = relevant_df[~relevant_df['is_cancelled']].dropna(subset=['delay_minutes'])
        
        avg_delay = valid_df['delay_minutes'].mean() if not valid_df.empty else 0
        severe_count = len(valid_df[valid_df['delay_minutes'] > 45])
        
        prob_miss_text = "N/A"
        is_high_risk = False
        
        if deadline_time:
            today = datetime.now().date()
            dt_deadline = datetime.combine(today, datetime.strptime(deadline_time, "%H:%M").time())
            dt_sched = datetime.combine(today, sched_arr)
            
            buffer_mins = (dt_deadline - dt_sched).total_seconds() / 60
            if buffer_mins < -720: 
                buffer_mins += 1440
            
            miss_count = len(valid_df[valid_df['delay_minutes'] > buffer_mins]) + cancel_count
            prob_miss = miss_count / total_relevant if total_relevant > 0 else 0
            prob_miss_text = f"{prob_miss:.1%}"
            is_high_risk = prob_miss > 0.15

        return {
            "total_flights": len(df),
            "relevant_flights": total_relevant,
            "hidden_flights": hidden_count,
            "cancellation_rate": f"{cancel_rate:.1%}",
            "average_delay_minutes": f"{avg_delay:+.0f}",
            "severe_delays_count": severe_count,
            "deadline_miss_probability": prob_miss_text,
            "is_high_risk": is_high_risk,
            "delay_distribution": valid_df['delay_minutes'].tolist() if not valid_df.empty else [],
            "metadata": {
                "route": f"{relevant_df['Origin'].mode()[0] if 'Origin' in relevant_df.columns else '?'} → {relevant_df['Destination'].mode()[0] if 'Destination' in relevant_df.columns else '?'}"
            }
        }
        
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}

def collect_flightaware_data(flight_identifier: str, api_key: str, months_back: int = 3) -> str:
    """Collect FlightAware data and format as CSV for analysis"""
    try:
        url = f"https://aeroapi.flightaware.com/aeroapi/flights/{flight_identifier}"
        headers = {"x-apikey": api_key}
        params = {"max_pages": max(1, months_back)}  # More pages for more history
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code != 200:
            return f"API Error {response.status_code}: {response.text}"
        
        data = response.json()
        flights = data.get('flights', [])
        if not flights:
            return "No flight history found"
        
        # Convert to CSV format
        csv_rows = []
        csv_rows.append("Date,Aircraft,Origin,Destination,Departure,Arrival,Duration")
        
        for f in flights:
            try:
                # Extract data
                origin = f.get('origin', {}).get('code', '?')
                dest = f.get('destination', {}).get('code', '?') 
                aircraft = f.get('aircraft_type', '?')
                status = f.get('status', '')
                
                # Handle times
                sched_out = f.get('scheduled_out')
                sched_in = f.get('scheduled_in')
                actual_out = f.get('actual_out')
                actual_in = f.get('actual_in') or f.get('estimated_in')
                
                if sched_out and sched_in:
                    # Convert to local times and format
                    sched_out_dt = pd.to_datetime(sched_out, utc=True)
                    sched_in_dt = pd.to_datetime(sched_in, utc=True)
                    
                    # Format date as DD-MMM-YY
                    date_str = sched_out_dt.strftime('%d-%b-%y')
                    
                    # Format times as HH:MMAM/PM
                    dep_time = sched_out_dt.strftime('%I:%M%p')
                    
                    if 'Cancelled' in status:
                        arr_time = "Cancelled"
                        duration = "Cancelled"
                    else:
                        if actual_in:
                            actual_in_dt = pd.to_datetime(actual_in, utc=True)
                            arr_time = actual_in_dt.strftime('%I:%M%p')
                            duration_mins = int((actual_in_dt - sched_out_dt).total_seconds() / 60)
                            duration = f"{duration_mins//60}h {duration_mins%60}m"
                        else:
                            arr_time = sched_in_dt.strftime('%I:%M%p')
                            duration = "Scheduled"
                    
                    csv_rows.append(f"{date_str},{aircraft},{origin},{dest},{dep_time},{arr_time},{duration}")
                    
            except Exception as e:
                continue  # Skip problematic entries
        
        if len(csv_rows) <= 1:
            return "No valid flight data could be processed"
        
        return "\n".join(csv_rows)
        
    except Exception as e:
        return f"Data collection failed: {str(e)}"

def generate_sample_csv(route: str = "BCN-CDG", days_back: int = 90) -> str:
    """Generate realistic sample CSV data for testing or demonstration"""
    import random
    from datetime import date, timedelta
    
    try:
        # Parse route
        if '-' in route:
            origin, dest = route.split('-', 1)
        else:
            origin, dest = "BCN", "CDG"
        
        csv_rows = []
        csv_rows.append("Date,Aircraft,Origin,Destination,Departure,Arrival,Duration")
        
        # Generate sample data
        aircraft_types = ["A320", "A20N", "A321", "B738"]
        base_dep_time = datetime.strptime("07:20", "%H:%M").time()
        base_arr_time = datetime.strptime("08:35", "%H:%M").time()
        
        for i in range(days_back):
            flight_date = date.today() - timedelta(days=i)
            date_str = flight_date.strftime('%d-%b-%y')
            
            # Simulate realistic variations
            dep_delay = random.randint(-5, 15)  # Usually 0-15 min late
            arr_delay = dep_delay + random.randint(-10, 20)  # Flight time variations
            
            # 5% chance of cancellation
            if random.random() < 0.05:
                aircraft = random.choice(aircraft_types)
                dep_time = (datetime.combine(date.today(), base_dep_time) + 
                           timedelta(minutes=dep_delay)).strftime('%I:%M%p')
                csv_rows.append(f"{date_str},{aircraft},{origin},{dest},{dep_time},Cancelled,Cancelled")
            else:
                aircraft = random.choice(aircraft_types)
                dep_time = (datetime.combine(date.today(), base_dep_time) + 
                           timedelta(minutes=dep_delay)).strftime('%I:%M%p')
                arr_time = (datetime.combine(date.today(), base_arr_time) + 
                           timedelta(minutes=arr_delay)).strftime('%I:%M%p')
                
                duration_mins = 75 + random.randint(-10, 20)  # ~1h 15m flight
                duration = f"{duration_mins//60}h {duration_mins%60:02d}m"
                
                csv_rows.append(f"{date_str},{aircraft},{origin},{dest},{dep_time},{arr_time},{duration}")
        
        return "\n".join(csv_rows)
        
    except Exception as e:
        return f"Sample generation failed: {str(e)}"

# --- MCP SERVER SETUP ---

server = Server("tail-risk-analyzer")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="analyze_csv_flight_data",
            description="Analyze flight delay and cancellation risk from CSV data using proven tail risk algorithms",
            inputSchema={
                "type": "object",
                "properties": {
                    "csv_content": {
                        "type": "string",
                        "description": "CSV content with flight data. Required columns: Date, Departure, Arrival. Optional: Origin, Destination, Aircraft, Duration"
                    },
                    "scheduled_time": {
                        "type": "string",
                        "description": "Your scheduled arrival time in HH:MM format (e.g., '16:45')"
                    },
                    "deadline_time": {
                        "type": "string", 
                        "description": "Optional deadline time in HH:MM format to calculate miss probability"
                    }
                },
                "required": ["csv_content", "scheduled_time"]
            }
        ),
        types.Tool(
            name="collect_flightaware_csv",
            description="Collect flight history from FlightAware API and format as CSV for analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "flight_identifier": {
                        "type": "string",
                        "description": "Flight identifier (e.g., 'VY6612', 'AA1234')"
                    },
                    "api_key": {
                        "type": "string",
                        "description": "FlightAware API key"
                    },
                    "months_back": {
                        "type": "integer",
                        "description": "Number of months of history to collect (1-6, default 3)",
                        "default": 3
                    }
                },
                "required": ["flight_identifier", "api_key"]
            }
        ),
        types.Tool(
            name="generate_sample_csv",
            description="Generate realistic sample CSV flight data for testing and demonstration purposes",
            inputSchema={
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "description": "Flight route in format ORIGIN-DESTINATION (e.g., 'BCN-CDG', 'JFK-LAX')",
                        "default": "BCN-CDG"
                    },
                    "days_back": {
                        "type": "integer", 
                        "description": "Number of days of sample data to generate (30-180, default 90)",
                        "default": 90
                    }
                },
                "required": []
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls"""
    print(f"Tool called: {name}", file=sys.stderr)
    
    if name == "analyze_csv_flight_data":
        try:
            csv_content = arguments["csv_content"]
            scheduled_time = arguments["scheduled_time"]
            deadline_time = arguments.get("deadline_time")
            
            # Process CSV data using proven function
            df, meta = process_csv_data(csv_content)
            if df is None:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"CSV processing failed: {meta}"})
                )]
            
            # Perform analysis using proven function
            analysis = analyze_tail_risk(df, scheduled_time, deadline_time)
            
            result = {
                "status": "success",
                "metadata": meta,
                "analysis": analysis
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
            
        except Exception as e:
            print(f"Tool execution error: {e}", file=sys.stderr)
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"Tool execution failed: {str(e)}"})
            )]
    
    elif name == "collect_flightaware_csv":
        try:
            flight_identifier = arguments["flight_identifier"]
            api_key = arguments["api_key"]
            months_back = arguments.get("months_back", 3)
            
            csv_content = collect_flightaware_data(flight_identifier, api_key, months_back)
            
            # Check if it's an error message
            if csv_content.startswith("API Error") or csv_content.startswith("No flight") or csv_content.startswith("Data collection failed"):
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": csv_content})
                )]
            
            result = {
                "status": "success",
                "flight_identifier": flight_identifier,
                "months_requested": months_back,
                "csv_content": csv_content,
                "rows_collected": len(csv_content.split('\n')) - 1  # Subtract header
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
            
        except Exception as e:
            print(f"CSV collection error: {e}", file=sys.stderr)
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"CSV collection failed: {str(e)}"})
            )]
    
    elif name == "generate_sample_csv":
        try:
            route = arguments.get("route", "BCN-CDG")
            days_back = arguments.get("days_back", 90)
            
            # Validate parameters
            days_back = max(30, min(180, days_back))  # Limit to 30-180 days
            
            csv_content = generate_sample_csv(route, days_back)
            
            if csv_content.startswith("Sample generation failed"):
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": csv_content})
                )]
            
            result = {
                "status": "success",
                "route": route,
                "days_generated": days_back,
                "csv_content": csv_content,
                "rows_generated": len(csv_content.split('\n')) - 1,
                "note": "This is simulated data for testing purposes only"
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
            
        except Exception as e:
            print(f"Sample generation error: {e}", file=sys.stderr)
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"Sample generation failed: {str(e)}"})
            )]
    
    else:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Unknown tool: {name}"})
        )]

async def main():
    """Run the server"""
    print("Starting Tail Risk Analysis MCP Server", file=sys.stderr)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
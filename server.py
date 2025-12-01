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
#!/usr/bin/env python3
"""
Test the simple server functions directly
"""

from server import process_csv_data, analyze_tail_risk
import json

def test_functions():
    """Test the server functions work correctly"""
    
    # Sample CSV data
    sample_csv = """Date,Aircraft,Origin,Destination,Departure,Arrival,Duration
21-Nov-25,A320,BCN,CDG,07:17AM,08:34AM,1h 17m
20-Nov-25,A20N,BCN,CDG,06:56AM,08:08AM,1h 12m
19-Nov-25,A320,BCN,CDG,07:15AM,08:45AM,1h 30m"""
    
    print("Testing CSV processing...")
    df, meta = process_csv_data(sample_csv)
    
    if df is not None:
        print(f"✓ CSV processed: {meta['count']} flights, {meta['origin']} -> {meta['dest']}")
        
        print("Testing analysis...")
        result = analyze_tail_risk(df, "08:30", "09:00")
        
        if "error" not in result:
            print("✓ Analysis completed successfully:")
            print(f"  Relevant flights: {result['relevant_flights']}")
            print(f"  Cancellation rate: {result['cancellation_rate']}")
            print(f"  Average delay: {result['average_delay_minutes']} min")
            print(f"  Miss probability: {result['deadline_miss_probability']}")
        else:
            print(f"✗ Analysis failed: {result['error']}")
    else:
        print(f"✗ CSV processing failed: {meta}")

if __name__ == "__main__":
    test_functions()
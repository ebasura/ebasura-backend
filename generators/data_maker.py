import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import StringIO

# Constants
BIN_IDS = [1, 2, 3]
WASTE_TYPES = [1, 2]
PAST_DAYS = 7 
FUTURE_DAYS = 0  
TIME_INTERVALS_PER_DAY = 24  
SEED = 42  # For reproducibility

# Function to generate synthetic data
def generate_synthetic_data(bin_ids, waste_types, past_days, future_days, time_intervals_per_day, seed=None):
    """
    Generates synthetic data for waste bin fill levels over a specified period.
    """
    np.random.seed(seed)  # Set seed for reproducibility
    data = []
    
    start_date = datetime.now() - timedelta(days=past_days)
    end_date = datetime.now() + timedelta(days=future_days)
    
    # Generate timestamps for each hour within the range
    timestamps = pd.date_range(start=start_date, end=end_date, freq='H')

    for bin_id in bin_ids:
        for waste_type in waste_types:
            fill_level = np.random.randint(5, 80)  # Initial fill level
            for timestamp in timestamps:
                # Reset fill level at midnight (0 hour) with a 30% probability (configurable)
                if timestamp.hour == 0 and np.random.random() > 0.7:
                    fill_level = np.random.randint(5, 20)

                # Simulate fill level change (normal distribution)
                fill_increase = np.random.normal(loc=2, scale=1)
                fill_level += fill_increase

                # Bound the fill level between 0 and 100
                fill_level = max(min(fill_level, 100), 0)

                data.append({
                    'bin_id': bin_id,
                    'waste_type': waste_type,
                    'timestamp': timestamp,
                    'fill_level': round(fill_level, 2)  # Round to 2 decimal places
                })

    return pd.DataFrame(data)

# Generate synthetic data
df = generate_synthetic_data(BIN_IDS, WASTE_TYPES, PAST_DAYS, FUTURE_DAYS, TIME_INTERVALS_PER_DAY, SEED)

# Function to generate SQL insert queries
def generate_sql_insert_queries(df):
    """
    Generates SQL insert queries for the given DataFrame.
    """
    queries = []
    for _, row in df.iterrows():
        timestamp_str = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        query = f"""
            INSERT INTO bin_fill_levels (bin_id, waste_type, timestamp, fill_level)
            VALUES ({row['bin_id']}, {row['waste_type']}, '{timestamp_str}', {row['fill_level']:.2f});
        """
        queries.append(query.strip())
    return queries

# Generate SQL queries
sql_queries = generate_sql_insert_queries(df)

# Write queries to a file efficiently using StringIO
def save_queries_to_file(queries, filename='bin_fill_levels_data.sql'):
    """
    Saves the generated SQL queries to a file.
    """
    with open(filename, 'w') as f:
        f.write("\n".join(queries))

# Save the queries to a file
save_queries_to_file(sql_queries)

print("SQL queries saved to 'bin_fill_levels_data.sql'")

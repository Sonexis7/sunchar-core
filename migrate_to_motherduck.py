import os
import duckdb
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('MOTHERDUCK_TOKEN')

if not token:
    raise ValueError('MOTHERDUCK_TOKEN not found in .env file!')

print('1. Connecting to MotherDuck Cloud service...')
con = duckdb.connect(f'md:?motherduck_token={token}')

print('2. Creating greenops_lakehouse database in the cloud...')
con.execute("CREATE DATABASE IF NOT EXISTS greenops_lakehouse;")
con.execute("USE greenops_lakehouse;")

print('3. Attaching local DuckDB lakehouse...')
local_path = '../uk-carbon-lakehouse/lakehouse/gold/analytics.duckdb'
con.execute(f"ATTACH '{local_path}' AS local_db (READ_ONLY);")

print('4. Replicating mart_green_compute_dispatch into greenops_lakehouse...')
con.execute("CREATE OR REPLACE TABLE mart_green_compute_dispatch AS SELECT * FROM local_db.mart_green_compute_dispatch;")

print('5. Verifying cloud tables:')
for t in con.execute("SHOW TABLES;").fetchall():
    print('   -', t[0])

row_count = con.execute("SELECT COUNT(*) FROM mart_green_compute_dispatch;").fetchone()[0]
print(f'Migration complete! {row_count} regional records replicated to MotherDuck.')
con.close()

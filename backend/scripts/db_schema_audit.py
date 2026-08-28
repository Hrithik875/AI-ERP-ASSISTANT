"""
DB schema audit — checks which tables and views exist.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.connection import execute_query

print("=== VIEWS ===")
try:
    r = execute_query("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
    for row in r:
        print(" ", list(row.values()))
except Exception as e:
    print("VIEWS error:", e)

print("\n=== BASE TABLES ===")
try:
    r = execute_query("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
    for row in r:
        print(" ", list(row.values()))
except Exception as e:
    print("BASE TABLES error:", e)

print("\n=== Checking vw_department_performance ===")
try:
    r = execute_query("SELECT * FROM vw_department_performance LIMIT 3")
    print("EXISTS, sample rows:", r[:2])
except Exception as e:
    print("ERROR:", e)

print("\n=== departments table ===")
try:
    r = execute_query("SELECT * FROM departments LIMIT 10")
    print("DEPARTMENTS rows:", r)
except Exception as e:
    print("ERROR:", e)

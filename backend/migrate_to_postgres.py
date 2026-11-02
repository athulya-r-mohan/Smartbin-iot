"""
Migration Script: SQLite (smartbin.db) -> PostgreSQL
Migrates all stored sensor readings, timestamps, and statuses into PostgreSQL.
Supports local PostgreSQL or Cloud PostgreSQL (Render, Supabase, Neon, etc.).
"""

import os
import sys
import sqlite3
import argparse
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def ensure_database_exists(host, port, user, password, dbname):
    """Connect to default 'postgres' db and create the target database if not exists."""
    print(f"Connecting to PostgreSQL server at {host}:{port} as user '{user}'...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname="postgres",
            connect_timeout=5
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone()
        if not exists:
            print(f"Database '{dbname}' does not exist. Creating it now...")
            cur.execute(f'CREATE DATABASE "{dbname}"')
            print(f"Database '{dbname}' created successfully!")
        else:
            print(f"Database '{dbname}' already exists.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Note: Could not check/create database '{dbname}' automatically ({e}). Assuming database already created.")

def create_postgres_tables(conn):
    """Create the sensor_readings table in PostgreSQL if it doesn't exist."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS sensor_readings (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        distance_cm REAL NOT NULL,
        fill_percentage INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL,
        is_valid BOOLEAN DEFAULT TRUE,
        source VARCHAR(50) DEFAULT 'ESP32'
    );
    CREATE INDEX IF NOT EXISTS ix_sensor_readings_id ON sensor_readings (id);
    CREATE INDEX IF NOT EXISTS ix_sensor_readings_timestamp ON sensor_readings (timestamp);
    CREATE INDEX IF NOT EXISTS ix_sensor_readings_status ON sensor_readings (status);
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    conn.commit()
    print("PostgreSQL table 'sensor_readings' and indexes verified.")

def migrate_data(sqlite_path, pg_conn):
    """Read all rows from SQLite and insert into PostgreSQL."""
    if not os.path.exists(sqlite_path):
        print(f"SQLite file not found at: {sqlite_path}")
        return 0

    sq_conn = sqlite3.connect(sqlite_path)
    sq_cur = sq_conn.cursor()
    sq_cur.execute("SELECT id, timestamp, distance_cm, fill_percentage, status, is_valid, source FROM sensor_readings ORDER BY id ASC")
    rows = sq_cur.fetchall()
    sq_conn.close()

    total_rows = len(rows)
    print(f"Found {total_rows} readings in SQLite ({sqlite_path}).")

    if total_rows == 0:
        print("No data to migrate.")
        return 0

    with pg_conn.cursor() as pg_cur:
        insert_sql = """
        INSERT INTO sensor_readings (id, timestamp, distance_cm, fill_percentage, status, is_valid, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """
        migrated_count = 0
        for r in rows:
            r_id, r_ts, r_dist, r_fill, r_status, r_valid, r_source = r
            if isinstance(r_ts, str):
                try:
                    ts_val = datetime.fromisoformat(r_ts)
                except ValueError:
                    ts_val = r_ts
            else:
                ts_val = r_ts

            pg_cur.execute(insert_sql, (
                r_id,
                ts_val,
                float(r_dist),
                int(r_fill),
                str(r_status),
                bool(r_valid),
                str(r_source or "ESP32")
            ))
            migrated_count += 1

        # Synchronize PostgreSQL serial sequence with the highest ID
        pg_cur.execute("""
            SELECT setval(
                pg_get_serial_sequence('sensor_readings', 'id'),
                COALESCE((SELECT MAX(id) FROM sensor_readings), 1)
            );
        """)
        pg_conn.commit()

    print(f"Successfully migrated {migrated_count} records into PostgreSQL!")
    return migrated_count

def run_migration_with_url(pg_url, sqlite_path="backend/smartbin.db"):
    # Fix Render url prefix
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    print(f"Connecting to PostgreSQL via URL...")
    conn = psycopg2.connect(pg_url)
    create_postgres_tables(conn)
    migrate_data(sqlite_path, conn)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sensor_readings")
        total = cur.fetchone()[0]
        cur.execute("SELECT id, timestamp, fill_percentage, status FROM sensor_readings ORDER BY id DESC LIMIT 3")
        latest = cur.fetchall()
        print(f"\n[VERIFICATION] Total rows in PostgreSQL: {total}")
        print("Latest 3 migrated records:")
        for row in latest:
            print(f"  ID: {row[0]} | Time: {row[1]} | Fill: {row[2]}% | Status: {row[3]}")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite smartbin.db to PostgreSQL")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL"), help="Full PostgreSQL connection URL (e.g. from Render)")
    parser.add_argument("--user", default="postgres", help="PostgreSQL user (default: postgres)")
    parser.add_argument("--password", help="PostgreSQL password")
    parser.add_argument("--host", default="localhost", help="PostgreSQL host (default: localhost)")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port (default: 5432)")
    parser.add_argument("--dbname", default="smartbindb", help="PostgreSQL database name (default: smartbindb)")
    parser.add_argument("--sqlite", default="backend/smartbin.db", help="Path to SQLite smartbin.db")
    args = parser.parse_args()

    if args.url and "postgresql" in args.url or (args.url and "postgres://" in args.url):
        run_migration_with_url(args.url, args.sqlite)
    elif args.password:
        ensure_database_exists(args.host, args.port, args.user, args.password, args.dbname)
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            dbname=args.dbname
        )
        create_postgres_tables(conn)
        migrate_data(args.sqlite, conn)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sensor_readings")
            print(f"\n[VERIFICATION] Total rows in PostgreSQL: {cur.fetchone()[0]}")
        conn.close()
    else:
        print("Error: Provide either --url <RENDER_POSTGRES_URL> or --password <LOCAL_PASSWORD>")
        sys.exit(1)

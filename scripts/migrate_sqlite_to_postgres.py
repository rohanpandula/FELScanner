#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script for FELScanner v2

This script migrates data from FELScanner v1 (SQLite) to v2 (PostgreSQL).

Usage:
    python migrate_sqlite_to_postgres.py --sqlite-db /path/to/felscanner.db --postgres-url postgresql://user:pass@localhost/felscanner

Requirements:
    - SQLite database file from FELScanner v1
    - Running PostgreSQL instance with schema initialized
    - Python 3.11+ with required dependencies
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from typing import Any

import asyncio
import asyncpg


class DatabaseMigrator:
    def __init__(self, sqlite_path: str, postgres_url: str):
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.sqlite_conn = None
        self.pg_pool = None

    async def connect(self):
        """Establish database connections"""
        print("Connecting to databases...")

        # SQLite connection
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row

        # PostgreSQL connection pool
        self.pg_pool = await asyncpg.create_pool(self.postgres_url, min_size=1, max_size=5)

        print("✓ Connected to both databases")

    async def close(self):
        """Close database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.pg_pool:
            await self.pg_pool.close()

    def get_sqlite_movies(self) -> list[dict[str, Any]]:
        """Fetch all movies from SQLite database"""
        print("\nFetching movies from SQLite...")

        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT * FROM movies")

        movies = []
        for row in cursor.fetchall():
            movie = dict(row)
            movies.append(movie)

        print(f"✓ Found {len(movies)} movies in SQLite")
        return movies

    def transform_movie_data(self, sqlite_movie: dict[str, Any]) -> dict[str, Any]:
        """Transform SQLite movie data to PostgreSQL format"""

        # Parse extra_data if it's a JSON string
        extra_data = {}
        if sqlite_movie.get('extra_data'):
            try:
                extra_data = json.loads(sqlite_movie['extra_data'])
            except (json.JSONDecodeError, TypeError):
                extra_data = {}

        # Map SQLite columns to PostgreSQL columns
        pg_movie = {
            'rating_key': sqlite_movie['rating_key'],
            'title': sqlite_movie['title'],
            'year': sqlite_movie.get('year'),
            'quality': sqlite_movie.get('quality', 'Unknown'),
            'codec': sqlite_movie.get('codec'),
            'resolution': sqlite_movie.get('resolution'),
            'dv_profile': sqlite_movie.get('dv_profile'),
            'dv_fel': bool(sqlite_movie.get('dv_fel', False)),
            'has_atmos': bool(sqlite_movie.get('has_atmos', False)),
            'file_path': sqlite_movie.get('file_path', ''),
            'file_size': sqlite_movie.get('file_size'),
            'added_at': datetime.fromisoformat(sqlite_movie['added_at']) if sqlite_movie.get('added_at') else datetime.now(),
            'updated_at': datetime.fromisoformat(sqlite_movie['updated_at']) if sqlite_movie.get('updated_at') else datetime.now(),
            'extra_data': json.dumps(extra_data) if extra_data else '{}',
        }

        return pg_movie

    async def migrate_movies(self, movies: list[dict[str, Any]]) -> int:
        """Migrate movies to PostgreSQL"""
        print(f"\nMigrating {len(movies)} movies to PostgreSQL...")

        migrated = 0
        skipped = 0
        errors = 0

        async with self.pg_pool.acquire() as conn:
            for movie in movies:
                try:
                    pg_movie = self.transform_movie_data(movie)

                    # Insert or update movie
                    await conn.execute("""
                        INSERT INTO movies (
                            rating_key, title, year, quality, codec, resolution,
                            dv_profile, dv_fel, has_atmos, file_path, file_size,
                            added_at, updated_at, extra_data
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                        )
                        ON CONFLICT (rating_key) DO UPDATE SET
                            title = EXCLUDED.title,
                            year = EXCLUDED.year,
                            quality = EXCLUDED.quality,
                            codec = EXCLUDED.codec,
                            resolution = EXCLUDED.resolution,
                            dv_profile = EXCLUDED.dv_profile,
                            dv_fel = EXCLUDED.dv_fel,
                            has_atmos = EXCLUDED.has_atmos,
                            file_path = EXCLUDED.file_path,
                            file_size = EXCLUDED.file_size,
                            updated_at = EXCLUDED.updated_at,
                            extra_data = EXCLUDED.extra_data
                    """,
                        pg_movie['rating_key'],
                        pg_movie['title'],
                        pg_movie['year'],
                        pg_movie['quality'],
                        pg_movie['codec'],
                        pg_movie['resolution'],
                        pg_movie['dv_profile'],
                        pg_movie['dv_fel'],
                        pg_movie['has_atmos'],
                        pg_movie['file_path'],
                        pg_movie['file_size'],
                        pg_movie['added_at'],
                        pg_movie['updated_at'],
                        pg_movie['extra_data']
                    )

                    migrated += 1

                    if migrated % 50 == 0:
                        print(f"  Migrated {migrated}/{len(movies)} movies...")

                except Exception as e:
                    print(f"  ✗ Error migrating movie '{movie.get('title')}': {e}")
                    errors += 1

        print(f"\n✓ Migration complete:")
        print(f"  - Migrated: {migrated}")
        print(f"  - Errors: {errors}")

        return migrated

    async def verify_migration(self) -> bool:
        """Verify migration integrity"""
        print("\nVerifying migration...")

        # Count movies in SQLite
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM movies")
        sqlite_count = cursor.fetchone()[0]

        # Count movies in PostgreSQL
        async with self.pg_pool.acquire() as conn:
            pg_count = await conn.fetchval("SELECT COUNT(*) FROM movies")

        print(f"  SQLite count: {sqlite_count}")
        print(f"  PostgreSQL count: {pg_count}")

        if sqlite_count == pg_count:
            print("✓ Verification successful: Row counts match")
            return True
        else:
            print(f"✗ Verification failed: Row count mismatch ({sqlite_count} vs {pg_count})")
            return False

    async def run_migration(self):
        """Execute the full migration process"""
        try:
            # Connect to databases
            await self.connect()

            # Fetch SQLite data
            movies = self.get_sqlite_movies()

            if not movies:
                print("No movies found in SQLite database. Nothing to migrate.")
                return

            # Confirm migration
            print(f"\n⚠️  About to migrate {len(movies)} movies from SQLite to PostgreSQL.")
            response = input("Continue? (yes/no): ")

            if response.lower() != 'yes':
                print("Migration cancelled.")
                return

            # Migrate data
            await self.migrate_movies(movies)

            # Verify migration
            await self.verify_migration()

            print("\n✓ Migration completed successfully!")

        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            sys.exit(1)

        finally:
            await self.close()


async def main():
    parser = argparse.ArgumentParser(
        description='Migrate FELScanner data from SQLite to PostgreSQL'
    )
    parser.add_argument(
        '--sqlite-db',
        required=True,
        help='Path to SQLite database file'
    )
    parser.add_argument(
        '--postgres-url',
        required=True,
        help='PostgreSQL connection URL (postgresql://user:pass@host/db)'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("FELScanner v1 → v2 Migration Tool")
    print("=" * 60)

    migrator = DatabaseMigrator(args.sqlite_db, args.postgres_url)
    await migrator.run_migration()


if __name__ == '__main__':
    asyncio.run(main())

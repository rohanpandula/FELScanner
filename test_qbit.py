#!/usr/bin/env python3
"""Quick test of qBittorrent integration"""
import asyncio
import sys
sys.path.insert(0, '/Users/rohan/Desktop/felscanner')

from integrations.qbittorrent import QBittorrentClient

async def test_qbit():
    client = QBittorrentClient(host="10.0.0.63", port=8080)

    print("Testing qBittorrent connection...")
    result = await client.test_connection()
    print(f"Result: {result}")

    if result['success']:
        print(f"✓ Connected to qBittorrent {result['version']}")
        print(f"✓ Found {result['torrent_count']} torrents")
    else:
        print(f"✗ Connection failed: {result.get('error')}")

    # Clean up
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_qbit())

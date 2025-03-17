# IPTScanner Module

This module integrates an IPTorrents scanner into the FELScanner web application.

## Overview

The IPTScanner monitors IPTorrents for new torrents matching a specific search term. By default, it searches for "BL+EL+RPU" which is used to find Dolby Vision content with both layers.

## Requirements

- Node.js (v14 or higher)
- Python 3.7 or higher
- Required Node.js packages:
  - puppeteer
  - node-cron
  - axios

## Setup

1. Install Node.js dependencies:
   ```
   cd iptscanner
   npm install puppeteer node-cron axios
   ```

2. Configure your IPTorrents login:
   - You will need the "uid" and "pass" cookies from a valid IPTorrents login
   - These can be entered in the Settings tab of the FELScanner web interface

## Features

- Monitors IPTorrents for new torrents matching your search criteria
- Configurable check schedule (from 15 minutes to daily)
- Displays results in a user-friendly table
- Tracks new torrents to highlight additions

## Configuration

All settings can be managed through the FELScanner web interface:

1. Enable/disable the scanner
2. Set custom search terms
3. Configure the check interval
4. Toggle headless mode
5. Set data paths
6. Enter IPTorrents login credentials

## Troubleshooting

- If the scanner fails to run, check the log in the IPTScanner tab
- Ensure your IPTorrents cookies are valid
- Make sure Node.js is installed and accessible on your system

## Notes

The actual scraping logic is handled by the `monitor-iptorrents.js` script, which is called by the Python wrapper. This design preserves the existing scraping logic while integrating it with the FELScanner web interface. 
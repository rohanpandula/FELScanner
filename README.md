# FELScanner

FELScanner is a web application that scans your Plex library for movies with Dolby Vision (focusing on Profile 7 FEL) and TrueHD Atmos content. It can create and manage collections in your Plex library based on these audio/video features, and includes an integrated IPTorrents scanner to monitor for new Dolby Vision content.

## Features

- **Advanced Dolby Vision Detection**: Identify movies with various Dolby Vision profiles, with special focus on Profile 7 FEL (Full Enhancement Layer)
- **TrueHD Atmos Detection**: Find movies with Dolby TrueHD Atmos audio tracks
- **Automatic Collection Management**: Create and maintain Plex collections for different content types
- **Detailed Reports**: Generate CSV and JSON reports with comprehensive movie information
- **Web Interface**: User-friendly interface with dark mode support
- **IPTorrents Scanner**: Integrated tool to monitor IPTorrents for new Dolby Vision content

## Configuration and Security

FELScanner requires credentials for several external services. To ensure security, sensitive information can be provided in two ways:

### Environment Variables

You can provide credentials via environment variables, which will take precedence over any settings in the configuration files:

```
# Plex configuration
PLEX_URL=http://your-plex-server:32400
PLEX_TOKEN=your_plex_token_here
LIBRARY_NAME=Movies

# Telegram configuration (optional)
TELEGRAM_ENABLED=true/false
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# IPTorrents configuration (optional)
IPT_UID=your_iptorrents_uid
IPT_PASS=your_iptorrents_passkey
```

See the `.env.example` file for a complete list of available environment variables.

### Settings Panel

All credentials and configuration options can also be set through the web interface's settings panel. However, for production deployments, using environment variables is recommended for better security.

### Security Best Practices

To keep your installation secure, follow these guidelines:

1. **Use Environment Variables**: Always use environment variables for credentials in production.
2. **Secure the Host**: Run the application behind a reverse proxy with HTTPS enabled.
3. **Limit Access**: Use authentication on your reverse proxy to restrict access to authorized users.
4. **Regular Updates**: Keep the application and its dependencies updated.
5. **Credential Isolation**: Use a dedicated Plex user with limited permissions for this application.

**Important Security Notes:**
- Never commit your `settings.json` file to version control
- Protect your Docker-Compose file if you include sensitive environment variables
- Set appropriate file permissions to restrict access to configuration files
- Use Docker volumes to persist settings outside the container

## Project Structure

### Core Components

- **`app.py`**: The main Flask application that handles routing, API endpoints, and orchestrates the scanning and collection management.
- **`scanner.py`**: The core scanning engine that connects to Plex, analyzes media files for Dolby Vision/Atmos features, and updates the internal database.
- **`templates/index.html`**: The single-page web interface template that provides access to all features.
- **`static/js/main.js`**: Client-side JavaScript handling UI interactions, API calls, and dynamic content rendering.

### IPTScanner Module

- **`iptscanner/`**: Directory containing the IPTorrents scanning functionality.
  - **`iptscanner.py`**: Python wrapper for the Node.js script, integrated with the main app.
  - **`monitor-iptorrents.js`**: Node.js script that handles the actual IPTorrents website scraping.
  - **`package.json`**: Node.js dependencies for the IPTScanner.

### Configuration Files

- **`settings.json`**: Stores application settings (created automatically on first run)
- **`requirements.txt`**: Python dependencies for the main application.
- **`docker-compose.yml`**: Configuration for running the application with Docker Compose.
- **`Dockerfile`**: Instructions for building the Docker image, including setup for both Python and Node.js environments.
- **`.env.example`**: Example environment variables file to copy and customize.

### Data Storage

- **`data/`**: Directory containing application data.
- **`exports/`**: Directory where scan reports and exports are stored.

## Installation

### Docker Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/FELScanner.git
cd FELScanner

# Copy the environment variables example file
cp .env.example .env

# Edit .env with your credentials
nano .env

# Start the container
docker-compose up -d
```

### Manual Installation

1. Install Python 3.10+ and Node.js 14+
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Node.js dependencies for IPTScanner:
   ```bash
   cd iptscanner
   npm install
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## First-Time Setup

1. Access the application at `http://your-server-ip:5000`
2. Follow the setup wizard to configure:
   - Plex server connection (URL and token)
   - Movie library to scan
   - Collection names
   - IPTorrents scanner settings (optional)

## Persistent Data

The application stores its data in the following locations:

- **Docker installation**: In the `/data` volume
- **Manual installation**: In the application directory

Important data files:
- `settings.json`: Configuration settings
- `data/movie_database.db`: SQLite database storing movie metadata
- `exports/`: Scan reports (CSV/JSON)
- `iptscanner/known_torrents.json`: List of previously detected torrents

## Troubleshooting

- **Plex Connection Issues**: Ensure your Plex URL includes the protocol (e.g., `http://your-plex-ip:32400`) and your token is valid.
- **IPTScanner Problems**: Verify your IPTorrents cookies are valid by using the "Test Login" button in settings.
- **Docker Networking**: Use `--network host` in Docker or the Host network type in Unraid to solve Plex connection issues.
- **Environment Variables**: If your settings aren't being applied, ensure environment variables are properly configured and that Docker has access to them.

## Development

FELScanner is built with:
- Python 3.10+ and Flask for the backend
- Bootstrap 5 for the frontend
- PlexAPI for Plex Media Server integration
- Node.js for the IPTorrents scraping functionality

## Credits

Developed by [rohanpandula](https://github.com/rohanpandula) 
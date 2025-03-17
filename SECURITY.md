# Security Best Practices for FELScanner

This document outlines the security measures implemented in FELScanner and provides best practices for secure deployment.

## Credential Management

FELScanner requires credentials for various external services:

- **Plex Media Server** - requires a server URL and authentication token
- **Telegram** (optional) - requires a bot token and chat ID
- **IPTorrents** (optional) - requires UID and passkey cookies

All credentials should be kept secure and not committed to version control.

## Environment Variables

The recommended way to provide credentials is through environment variables:

```
# Plex configuration
PLEX_URL=http://your-plex-server:32400
PLEX_TOKEN=your_plex_token_here
LIBRARY_NAME=Movies

# Telegram configuration
TELEGRAM_ENABLED=true/false
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# IPTorrents configuration
IPT_UID=your_iptorrents_uid
IPT_PASS=your_iptorrents_passkey
```

Environment variables take precedence over settings in the settings.json file.

## Secure Deployment

1. **Use Docker volumes** to persist data and settings outside the container
2. **Run behind a reverse proxy** that provides HTTPS encryption (e.g., Nginx, Traefik)
3. **Add authentication** to your reverse proxy to limit access
4. **Use a dedicated network** for your Docker containers
5. **Regularly update** the application and its dependencies
6. **Use secrets** in Docker Swarm or Kubernetes rather than environment variables for production deployments

## File Permissions

When running outside of Docker:

1. Ensure settings.json and other credential files are readable only by the user running the application
2. Set appropriate permissions on data directories (700 or 750)
3. Do not run the application as root

## Settings Storage

The application stores settings in:

- **settings.json** - Main application settings
- **iptscanner/config.json** - IPTScanner module settings
- **iptscanner/cookies.json** - IPTorrents cookies

All these files are excluded from version control in .gitignore.

## Secure Coding Practices

The application follows these secure coding practices:

1. No hardcoded credentials
2. Environment variables prioritized over configuration files
3. Sensitive information is not logged
4. Authentication tokens are not exposed in the UI

## Issues and Vulnerability Reporting

If you discover a security vulnerability or have concerns about the application's security, please report it responsibly by contacting the project maintainer directly rather than opening a public issue.

## Recommendations for Self-Hosted Applications

1. **Network Isolation**: Consider running this application on an isolated VLAN or network segment
2. **Limited Access**: Only allow access from trusted networks
3. **Least Privilege**: Use API keys and tokens with minimum necessary permissions
4. **Monitoring**: Set up monitoring and alerting for unusual activity

Remember that security is a continuous process, not a one-time setup. 
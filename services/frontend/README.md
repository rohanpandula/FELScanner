# FELScanner v2 Frontend

Modern Vue 3 + Vite + TypeScript frontend for FELScanner.

## Features

- **Vue 3 Composition API** - Modern reactive framework
- **TypeScript** - Type-safe development
- **Vite** - Fast HMR and optimized builds
- **Pinia** - Intuitive state management
- **Tailwind CSS** - Utility-first styling
- **Chart.js** - Data visualizations

## Development

```bash
# Install dependencies
npm install

# Start dev server (with HMR)
npm run dev

# Type check
npm run build

# Run unit tests
npm run test:unit

# Run E2E tests
npm run test:e2e

# Lint and fix
npm run lint

# Format code
npm run format
```

## Project Structure

```
src/
├── api/           # API client layer
├── assets/        # Static assets and global CSS
├── components/    # Reusable components
├── composables/   # Vue composables
├── router/        # Vue Router configuration
├── stores/        # Pinia stores
├── views/         # Page components
├── App.vue        # Root component
└── main.ts        # Application entry point
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `VITE_API_BASE_URL` - Backend API base URL (default: http://localhost:8000/api)

## Views

- **Dashboard** - Library statistics, scan controls, connection status
- **Metadata Explorer** - Movie search, filtering, detailed metadata viewer
- **Downloads** - Pending approvals, active torrents, download history
- **IPT Scanner** - IPTorrents cache browser and scan trigger

## Stores

- **app** - Scan status, connections, auto-refresh, flash messages
- **movies** - Movie list, filtering, pagination, statistics
- **downloads** - Pending downloads, active torrents, history
- **metadata** - Movie metadata, ffprobe data, versions
- **settings** - Configuration management

## API Integration

All API calls go through the centralized API client layer (`src/api/`) with:

- Type-safe request/response interfaces
- Automatic error handling
- Request/response interceptors
- Base URL configuration

## Build for Production

```bash
npm run build
```

Output will be in `dist/` directory, ready to be served by Nginx or any static file server.

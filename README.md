# HTTP File Server

Blob storage server over HTTP.

## Setup

```bash
npm install
```

## Run

```bash
npm start        # production
npm run dev      # watch mode (auto-restart on changes)
```

Server starts on `http://localhost:3000` by default. Override with `PORT` env var.

## API

| Method   | Path           | Description         |
|----------|----------------|---------------------|
| `POST`   | `/blobs/:id`   | Create/update blob  |
| `GET`    | `/blobs/:id`   | Retrieve blob       |
| `DELETE` | `/blobs/:id`   | Delete blob         |

## Project Structure

```
src/
  server.js          # Entry point, warmup, app setup
  config.js          # All constants (limits, paths)
  routes/
    blobs.js         # POST / GET / DELETE route handlers
data/                # Blob storage (gitignored)
```

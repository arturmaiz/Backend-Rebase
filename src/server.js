const express = require('express');
const fs = require('fs');
const { PORT, DATA_DIR } = require('./config');
const blobsRouter = require('./routes/blobs');

async function warmup() {
  await fs.promises.mkdir(DATA_DIR, { recursive: true });
  // TODO: any startup calculations / cleanups go here
}

async function main() {
  await warmup();

  const app = express();

  app.use('/blobs', blobsRouter);

  app.listen(PORT, () => {
    console.log(`Server listening on port ${PORT} 🍔`);
  });
}

main().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});

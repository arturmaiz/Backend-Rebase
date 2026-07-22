const express = require('express');
const router = express.Router();

// POST /blobs/:id — store (upsert) a blob
router.post('/:id', (req, res) => {
  // TODO: validate id
  // TODO: validate Content-Length header
  // TODO: validate payload length, disk quota, blob count
  // TODO: extract storable headers (Content-Type, x-rebase-*)
  // TODO: validate header constraints
  // TODO: stream body to disk
  // TODO: persist metadata (stored headers)
  res.status(201).json({ message: 'created' });
});

// GET /blobs/:id — retrieve a blob
router.get('/:id', (req, res) => {
  // TODO: validate id
  // TODO: check blob exists → 404 if not
  // TODO: read stored headers and set them on response
  // TODO: fallback Content-Type to application/octet-stream
  // TODO: stream file to response
  res.status(404).json({ error: 'not found' });
});

// DELETE /blobs/:id — delete a blob
router.delete('/:id', (req, res) => {
  // TODO: validate id
  // TODO: delete blob + metadata from disk (no 404 needed)
  res.status(204).end();
});

module.exports = router;

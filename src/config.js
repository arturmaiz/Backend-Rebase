const path = require('path');

const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, '..', 'data');

const MAX_PAYLOAD_LENGTH = 10 * 1024 * 1024;   // 10 MB
const MAX_DISK_QUOTA = 1024 * 1024 * 1024;      // 1 GB
const MAX_HEADER_KEY_LENGTH = 30;
const MAX_HEADER_VALUE_LENGTH = 400;
const MAX_HEADER_COUNT = 20;
const MAX_ID_LENGTH = 200;
const MAX_BLOBS_TOTAL = 1_000_000;
const MAX_BLOBS_IN_FOLDER = 1000;               // Level 3

const VALID_ID_REGEX = /^[a-zA-Z0-9._-]+$/;

module.exports = {
  PORT,
  DATA_DIR,
  MAX_PAYLOAD_LENGTH,
  MAX_DISK_QUOTA,
  MAX_HEADER_KEY_LENGTH,
  MAX_HEADER_VALUE_LENGTH,
  MAX_HEADER_COUNT,
  MAX_ID_LENGTH,
  MAX_BLOBS_TOTAL,
  MAX_BLOBS_IN_FOLDER,
  VALID_ID_REGEX,
};

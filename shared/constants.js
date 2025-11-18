'use strict';

const MIME_WHITELIST = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB
const DEFAULT_UPLOAD_DIR = 'backend/uploads';

module.exports = {
  MIME_WHITELIST,
  MAX_UPLOAD_BYTES,
  DEFAULT_UPLOAD_DIR
};



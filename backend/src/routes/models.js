'use strict';

const path = require('path');
const express = require('express');
const { readJson } = require('../utils/jsonStore');

const router = express.Router();
const MODELS_FILE = path.resolve(__dirname, '../../data/models.json');

router.get('/', async (_req, res, next) => {
  try {
    const list = await readJson(MODELS_FILE);
    res.json(list);
  } catch (err) {
    next(err);
  }
});

module.exports = router;



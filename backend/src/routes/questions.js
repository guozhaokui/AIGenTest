'use strict';

const path = require('path');
const express = require('express');
const { readJson } = require('../utils/jsonStore');

const router = express.Router();
const DATA_FILE = path.resolve(__dirname, '../../data/questions.json');

router.get('/', async (_req, res, next) => {
  try {
    const data = await readJson(DATA_FILE);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

module.exports = router;



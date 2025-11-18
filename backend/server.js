'use strict';

const app = require('./src/app');

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  /* eslint-disable no-console */
  console.log(`Backend listening on http://localhost:${PORT}`);
});



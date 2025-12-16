const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const databaseFile = path.join(__dirname, 'database.sqlite');
const db = new sqlite3.Database(databaseFile);

function initialize() {
  db.serialize(() => {
    db.run(
      `CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        originalname TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        thumbnail_filename TEXT
      )`
    );

    db.run(
      'ALTER TABLE videos ADD COLUMN IF NOT EXISTS thumbnail_filename TEXT;'
    );
  });
}

module.exports = {
  db,
  initialize,
};

const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const ffmpeg = require('fluent-ffmpeg');
const ffmpegPath = require('ffmpeg-static');
const { db, initialize } = require('./database');

ffmpeg.setFfmpegPath(ffmpegPath);

const app = express();
const port = process.env.PORT || 3000;

const uploadDir = path.join(__dirname, 'public', 'uploads', 'videos');
const thumbnailDir = path.join(__dirname, 'public', 'uploads', 'thumbnails');

fs.mkdirSync(uploadDir, { recursive: true });
fs.mkdirSync(thumbnailDir, { recursive: true });

initialize();

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) => {
    const parsed = path.parse(file.originalname);
    const uniqueName = `${parsed.name}-${Date.now()}${parsed.ext}`;
    cb(null, uniqueName);
  },
});

const upload = multer({ storage });

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function createThumbnail(videoPath, thumbnailName) {
  const outputPath = path.join(thumbnailDir, thumbnailName);

  return new Promise((resolve, reject) => {
    ffmpeg(videoPath)
      .seekInput('00:00:01')
      .frames(1)
      .outputOptions(['-q:v 2'])
      .output(outputPath)
      .on('end', () => resolve(thumbnailName))
      .on('error', reject)
      .run();
  });
}

app.post('/upload', upload.single('video'), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No video file uploaded.' });
  }

  try {
    const videoPath = path.join(uploadDir, req.file.filename);
    const thumbnailName = `${path.parse(req.file.filename).name}.jpg`;

    await createThumbnail(videoPath, thumbnailName);

    db.run(
      `INSERT INTO videos (filename, originalname, thumbnail_filename) VALUES (?, ?, ?)`,
      [req.file.filename, req.file.originalname, thumbnailName],
      function (err) {
        if (err) {
          console.error('Failed to save video metadata:', err);
          return res
            .status(500)
            .json({ error: 'Failed to save video information.' });
        }

        res.status(201).json({
          id: this.lastID,
          filename: req.file.filename,
          originalname: req.file.originalname,
          thumbnail_filename: thumbnailName,
        });
      }
    );
  } catch (error) {
    console.error('Failed to process upload:', error);
    res.status(500).json({ error: 'Failed to process video upload.' });
  }
});

app.get('/api/videos', (req, res) => {
  db.all(
    `SELECT id, filename, originalname, created_at, thumbnail_filename FROM videos ORDER BY created_at DESC`,
    (err, rows) => {
      if (err) {
        console.error('Failed to fetch videos:', err);
        return res.status(500).json({ error: 'Failed to retrieve videos.' });
      }

      res.json(rows);
    }
  );
});

app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});

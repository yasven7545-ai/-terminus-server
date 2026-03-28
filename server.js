const express = require("express");
const path = require("path");
const xlsx = require("xlsx");
const multer = require("multer");
const app = express();
const PORT = 3000;

// Serve frontend static files
app.use(express.static(path.join(__dirname, "public")));
app.use(express.json());

// Uploads config (for Upload tab)
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, path.join(__dirname, "data")),
  filename: (req, file, cb) => cb(null, "data.xlsx")
});
const upload = multer({ storage });

// Route: Read Excel data
app.get("/api/vacant-data", (req, res) => {
  try {
    const filePath = path.join(__dirname, "data", "data.xlsx");
    const workbook = xlsx.readFile(filePath);
    const sheetName = workbook.SheetNames[0];
    const data = xlsx.utils.sheet_to_json(workbook.Sheets[sheetName]);
    res.json(data);
  } catch (err) {
    console.error("Error reading Excel:", err);
    res.status(500).json({ error: "Failed to read Excel file" });
  }
});

// Route: Upload new Excel
app.post("/api/upload", upload.single("file"), (req, res) => {
  res.send("✅ Excel uploaded successfully!");
});

// Start server
app.listen(PORT, () => console.log(`🚀 Server running at http://localhost:${PORT}`));

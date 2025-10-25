RPA: Limmatwelle → Würenlos Baugesuch Extractor

End-to-end automation that:

Downloads the correct Limmatwelle e-paper issue (Issuu viewer).

Parses page 12 and extracts the two Würenlos “Baugesuchspublikation” boxes (bottom left & bottom right).

Outputs clean JSON with normalized fields.

Works even when the PDF is scanned (OCR fallback) or the text layer is messy (labels glued, broken newlines, soft hyphens, etc.).

✨ Highlights

Resilient scraping of Issuu viewer (performance‐log sniff + multiple download fallbacks).

Text-layer first, OCR fallback (pypdfium2 + Tesseract) for speed and reliability.

Robust parsing with tolerant header/footer detection and label slicing.

Right-box rescue pass to fix typical OCR contamination (e.g., Bauvorhaben swallowing Lage).

Deterministic normalization (dashes, umlauts, single footer, dehyphenation).

📦 Project Structure
.
├─ baugesuch_reader.py        # PDF/OCR parsing → 2 JSON objects
├─ epaper_downloader.py       # Selenium/Chrome: fetch the PDF
├─ tasks.robot                # Robot Framework task wiring
├─ robot.yaml                 # rcc entrypoint / tasks
├─ conda.yaml                 # pinned runtime (python, libs)
├─ resources/
│  └─ db.cfg                  # (placeholder, if you persist results)
├─ input/
│  └─ limmatwelle-22-mai.pdf  # downloaded PDF goes here
├─ output/                    # logs & JSON appear here
└─ README.md                  # you are here

✅ Output Schema (per object)
{
  "Bauherrschaft": "string",
  "Bauvorhaben": "string",
  "Lage": "string",
  "Zone": "string",
  "Zusatzgesuch": "string",
  "others": "string"
}


Example (expected):

[
  {
    "Bauherrschaft": "Ortsbürgergemeinde Würenlos, Schulstrasse 26, 5436 Würenlos",
    "Bauvorhaben": "Dachsanierung",
    "Lage": "Parzelle 4885 (Plan 25), Forsthaus Tägerhard",
    "Zone": "Ausserhalb Bauzone – Wald",
    "Zusatzgesuch": "Departement Bau, Verkehr und Umwelt",
    "others": "Gesuchsauflage vom 23. Mai bis 23. Juni 2025 … BAUVERWALTUNG WÜRENLOS"
  },
  {
    "Bauherrschaft": "Markwalder René, Bünternstrasse 43, 5436 Würenlos",
    "Bauvorhaben": "Erweiterung Silolanlage und Umnutzung Stall (teilweise) in Milchkuhliegeboxen",
    "Lage": "Parzelle 3105 (Plan 33), Bünternstrasse 43",
    "Zone": "Ausserhalb Bauzone – Landschaftsschutzzone",
    "Zusatzgesuch": "Departement Bau, Verkehr und Umwelt",
    "others": "Gesuchsauflage vom 23. Mai bis 23. Juni 2025 … BAUVERWALTUNG WÜRENLOS"
  }
]

🛠 Requirements

Windows 10/11

Chrome (recent)

Tesseract OCR (Windows installer)

Default path used: C:\Program Files\Tesseract-OCR\tesseract.exe

Adjust inside baugesuch_reader.py if different.

rcc (recommended) or plain Python

Network access to: https://www.limmatwelle.ch/e-paper and Issuu CDN

🔧 Setup (with rcc – recommended)

Install rcc
Download from Robocorp or include the provided rcc.exe.

Clone the repo

git clone https://github.com/faisalakbar/python-end-to-end-project-scraping-pdf.git
cd python-end-to-end-project-scraping-pdf


Ensure Chrome + Tesseract are installed

Verify tesseract.exe lives at C:\Program Files\Tesseract-OCR\tesseract.exe

Otherwise update TESSERACT_EXE in baugesuch_reader.py.

Run

rcc run


What it does:

Uses epaper_downloader.py to fetch the target issue PDF into input/.

Runs baugesuch_reader.py to parse page 12 into output/baugesuch.json.

Robot logs go under output/.

🔧 Setup (plain Python)

Create venv / conda env and install deps in conda.yaml:

selenium

pypdfium2

pypdf

pytesseract

Pillow

rpaframework (for RPA.PDF fast-path)

Run the downloader

python epaper_downloader.py


It saves: input/limmatwelle-22-mai.pdf

Run the parser

python -c "import baugesuch_reader as b; print(b.parse_baugesuch_from_pdf(r'input/limmatwelle-22-mai.pdf', 12, r'output/baugesuch.json'))"

⚙️ How it Works

Downloader (epaper_downloader.py)

Opens e-paper page, scrolls to card containing “Woche 21” + “22. Mai”.

Opens Issuu viewer and tries multiple Download selectors.

As a fallback, sniffs Chrome performance logs for application/pdf and handles automatic save.

Parser (baugesuch_reader.py)

Fast path: try text layer (RPA.PDF / pypdf).

Fallback: render page → OCR with Tesseract.

Find header→footer blocks (Baugesuchspublikation … BAUVERWALTUNG WÜRENLOS).

Slice fields by label positions (handles “Lage:Bauvorhaben:” glued labels).

Right-box rescue: fixes common contamination; prefers canonical patterns like
Parzelle (\d+) (Plan N), …strasse NN.

Normalize dashes (–), diacritics, spaces, footer duplication, etc.

▶️ Robot Task

tasks.robot defines a single task that:

Downloads the issue.

Parses page 12.

Writes JSON to output/baugesuch.json.

You can run it via:

rcc run

🔍 Troubleshooting

“No keyword with name 'Download Issue Pdf' found.”
Ensure your Robot task uses the Python module as a Library or runs the Python script directly (the provided robot.yaml/tasks.robot already do this).

No PDF downloaded
The Issuu UI changes sometimes. The script tries multiple selectors and also performance log sniffing. Make sure Chrome is up to date and site is reachable.

OCR looks wrong / JSON empty
Check:

output/page_text_debug.txt (full page text/OCR)

Ensure TESSERACT_EXE is correct.

pypdfium2 installed (PDF → image).

Git push rejected (non-fast-forward)

git pull --rebase origin main
# resolve conflicts if any
git push -u origin main

🧪 Quick Local Test
python - << "PY"
import json, baugesuch_reader as b
out = b.parse_baugesuch_from_pdf(r"input/limmatwelle-22-mai.pdf", 12, r"output/baugesuch.json")
print(json.dumps(json.loads(out), ensure_ascii=False, indent=2))
PY

🧹 Coding Notes / Performance

Text layer first to avoid OCR cost when possible.

Single render pass (whole page) for OCR; no fragile manual crops needed.

Compiled regex for hot paths.

Rescue pass only when needed (heuristics keep happy path fast).

Deterministic normalization ensures clean, stable output.

📄 License

MIT — see LICENSE.

📬 Submission

As requested, the code is available here:
GitHub: https://github.com/faisalakbar/python-end-to-end-project-scraping-pdf

If you need a zipped artifact or a Dockerized runner, say the word and I’ll add it.
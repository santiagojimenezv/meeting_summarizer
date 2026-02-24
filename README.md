# Meeting Summarizer

A Python utility that automatically summarizes video recordings of meetings using Google's Gemini AI API, with a focus on **precision** and **minimal hallucination**.

## Features

- **Two-pass pipeline**: Transcribe → Summarize for higher accuracy
- **Anti-hallucination guardrails**: Strict prompt rules prevent fabricated dates, names, and facts
- **Auto-context**: Loads `amaze_projects.md` by default for correct name spellings and project context
- **Filename metadata extraction**: Extracts date and meeting name from filenames — no guessing
- **Post-generation validation**: `validate.py` checks summaries for common errors
- **Multi-format support**: `.mov`, `.mp4`, `.webm`, `.m4a`, `.mp3`
- **Transcript saving**: Raw transcripts saved to `transcripts/` for auditing and search

## Requirements

- Python 3.x
- Google Gemini API key ([get one here](https://aistudio.google.com/apikey))

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

1. Place media files in the `input/` directory
2. Run the summarizer:
   ```bash
   python3 summarize.py
   ```
3. Find summaries in `output/` and transcripts in `transcripts/`
4. Processed videos are moved to `processed/`

### Context Options

Context is automatically loaded from `amaze_projects.md` if present. You can override this:

```bash
# Use a different context file
python3 summarize.py --context path/to/context.md

# Run without any context
python3 summarize.py --no-context
```

### Validating Summaries

After generating summaries, run the validator to check for issues:

```bash
# Validate all summaries in output/
python3 validate.py

# Validate specific files
python3 validate.py output/2026-02-23*_summary.md
```

The validator checks for:
- **Date mismatches** between filename and summary content
- **Name misspellings** against the context file roster
- **Missing sections** in the expected format
- **Potential hallucinations** from inaudible transcript segments

## Directory Structure

```
├── input/         # Drop media files here (.mov, .mp4, .webm, .m4a, .mp3)
├── output/        # Generated summaries (.md)
├── transcripts/   # Raw transcripts (.md) — for auditing and search
├── processed/     # Archived videos after processing
├── summarize.py   # Main script (two-pass pipeline)
├── validate.py    # Post-generation validation
└── amaze_projects.md  # Default context file
```

## Output

For each meeting file, three artifacts are produced:

| File | Location | Purpose |
|------|----------|---------|
| `*_summary.md` | `output/` | Structured meeting summary |
| `*_transcript.md` | `transcripts/` | Verbatim transcript with speaker labels |
| `*_validation.md` | (stdout) | Issues found during validation |

## How It Works

```
┌─────────────┐    Pass 1     ┌──────────────┐    Pass 2     ┌─────────────┐
│  Video/Audio │──────────────▶│  Transcript  │──────────────▶│   Summary   │
│  (.mov etc.) │  transcribe  │  (verbatim)  │  summarize   │ (structured)│
└─────────────┘              └──────────────┘              └─────────────┘
                                    │                             │
                             ┌──────▼──────┐              ┌──────▼──────┐
                             │ transcripts/ │              │   output/   │
                             └─────────────┘              └─────────────┘
```

The two-pass approach means:
1. **Pass 1** focuses purely on accurate speech-to-text with speaker identification
2. **Pass 2** focuses purely on text summarization — a much more reliable task than video-to-text summarization

# Meeting Summarizer

A Python utility that automatically summarizes video recordings of meetings using Google's Gemini AI API.

## Features

- Processes `.mov` video files and generates structured markdown summaries
- Extracts key decisions, action items, participants, and discussion points
- Automatically archives processed videos

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

1. Place `.mov` files in the `input/` directory
2. Run the script:
   ```bash
   python3 summarize.py
   ```
3. Find summaries in `output/` as markdown files
4. Processed videos are moved to `processed/`

## Directory Structure

```
├── input/       # Drop .mov files here
├── output/      # Generated summaries (.md)
├── processed/   # Archived videos after processing
├── summarize.py # Main script
└── list_models.py # Utility to list available Gemini models
```

## Output Format

Summaries include:
- Meeting overview (participants, date)
- Executive summary
- Key discussion points
- Decisions made
- Action items (with owner, deadline, priority)
- Open questions
- Next steps

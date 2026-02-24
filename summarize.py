import os
import re
import time
import glob
import shutil
import argparse
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("Error: GEMINI_API_KEY not found in .env file.")
    print("Please copy .env.example to .env and add your API key.")
    exit(1)

genai.configure(api_key=API_KEY)

INPUT_DIR = "input"
OUTPUT_DIR = "output"
PROCESSED_DIR = "processed"
TRANSCRIPT_DIR = "transcripts"

# Default context file (auto-loaded if present)
DEFAULT_CONTEXT_FILE = "amaze_projects.md"

# Supported media formats
SUPPORTED_EXTENSIONS = (".mov", ".mp4", ".webm", ".m4a", ".mp3")

# Model configuration
MODEL = "gemini-2.5-flash"
GENERATION_CONFIG = genai.types.GenerationConfig(
    temperature=0.2,  # Low temperature for factual accuracy
)

# ─── Prompts ────────────────────────────────────────────────────────────────────

TRANSCRIPTION_PROMPT = """Transcribe this meeting recording into a detailed, verbatim transcript.

## Rules:
1. Identify each speaker by name when possible. If a speaker's name is unclear, label them as "Speaker 1", "Speaker 2", etc.
2. Include timestamps at the start of each speaker turn in [MM:SS] format.
3. Transcribe what was actually said — do NOT paraphrase, summarize, or omit anything.
4. If a word or phrase is unclear, write [inaudible] rather than guessing.
5. Note any significant non-verbal events in [brackets], e.g., [screen sharing starts], [laughter], [someone joins the call].

## Context (use ONLY for identifying speakers, NOT for content):
{context}

## Format:
[MM:SS] **Speaker Name**: What they said verbatim.
"""

SUMMARY_PROMPT = """You are a precise meeting summarizer. Analyze the transcript below and create a structured summary in Markdown format.

## CRITICAL RULES — Follow these strictly:
1. Only include information **explicitly stated** in the transcript. Do NOT infer, guess, or fabricate any facts.
2. The meeting date is: **{meeting_date}**. Use this date EXACTLY — do not guess or infer a different date.
3. The meeting title is: **{meeting_name}**. Use this title EXACTLY.
4. For participant names: use the EXACT spelling from the context document below. If a name is unclear in the transcript, write it phonetically and mark it with [unclear].
5. For decisions and action items: only list items that were **explicitly agreed upon** during the meeting. Do not infer implied decisions.
6. If information for a section is not discussed, write "Not discussed in this meeting" — do NOT fabricate content.
7. When attributing statements or actions to people, only attribute what they **explicitly said or committed to**.
8. Do NOT start the summary with a preamble paragraph — begin directly with the first section heading.

## Context:
{context}

## Required Sections:

## 1. Meeting Overview
- **Meeting Title**: {meeting_name}
- **Date**: {meeting_date}
- **Duration**: (only if discernible from timestamps)
- **Participants**: (list all attendees with their roles if mentioned in context or recording)

## 2. Executive Summary
A 2-3 paragraph high-level summary of what was discussed and accomplished in this meeting.

## 3. Key Discussion Points
For each major topic discussed:
- **Topic name**: Detailed explanation of what was discussed
- Include context, concerns raised, and conclusions reached

## 4. Decisions Made
List all decisions with:
- The decision itself
- Who made or approved it
- Any conditions or caveats

## 5. Action Items
Create a table with:
| Action Item | Owner | Deadline | Priority |
|-------------|-------|----------|----------|
| Task description | Person responsible | Due date if mentioned | High/Medium/Low |

## 6. Open Questions / Parking Lot
Any unresolved questions or topics deferred for later discussion.

## 7. Next Steps
What happens after this meeting? Any follow-up meetings scheduled?

---
## Transcript to summarize:

{transcript}
"""

# ─── Helpers ────────────────────────────────────────────────────────────────────

# Create directories if they don't exist
for d in (INPUT_DIR, OUTPUT_DIR, PROCESSED_DIR, TRANSCRIPT_DIR):
    os.makedirs(d, exist_ok=True)


def extract_metadata_from_filename(filename):
    """Extract date and meeting name from filename pattern.
    
    Expected patterns:
        "2026-02-23 13-01-29-Amaze-Stand-up.mov"
        "2026-02-23 13-01-29_Amaze-Stand-up.mov"
        "2026-02-23 13-01-29_Amaze_Stand_up.mov"
    
    Returns:
        (date_str, meeting_name) or (None, None) if pattern doesn't match.
    """
    base = os.path.splitext(os.path.basename(filename))[0]

    # Match date portion: YYYY-MM-DD
    match = re.match(r"(\d{4}-\d{2}-\d{2})\s+\d{2}-\d{2}-\d{2}[_-]?(.*)", base)
    if match:
        date_str = match.group(1)
        raw_name = match.group(2)
        # Clean up the meeting name: replace _ and - with spaces, collapse whitespace
        meeting_name = re.sub(r"[-_]+", " ", raw_name).strip()
        return date_str, meeting_name

    return None, None


def load_context(context_path):
    """Load context from a markdown file."""
    if not os.path.exists(context_path):
        return None

    with open(context_path, "r") as f:
        return f.read()


# ─── Core Pipeline ──────────────────────────────────────────────────────────────

def transcribe_video(video_file, context):
    """Pass 1: Generate a verbatim transcript from the video."""
    prompt = TRANSCRIPTION_PROMPT.format(
        context=context if context else "No additional context provided."
    )

    model = genai.GenerativeModel(model_name=MODEL)
    response = model.generate_content(
        [video_file, prompt],
        generation_config=GENERATION_CONFIG,
        request_options={"timeout": 600},
    )
    return response.text


def summarize_transcript(transcript, context, meeting_date, meeting_name):
    """Pass 2: Summarize the transcript into structured markdown."""
    prompt = SUMMARY_PROMPT.format(
        context=context if context else "No additional context provided.",
        transcript=transcript,
        meeting_date=meeting_date if meeting_date else "Date not available",
        meeting_name=meeting_name if meeting_name else "Meeting",
    )

    model = genai.GenerativeModel(model_name=MODEL)
    response = model.generate_content(
        prompt,
        generation_config=GENERATION_CONFIG,
        request_options={"timeout": 600},
    )
    return response.text


def process_meeting(video_path, context=None):
    """Full pipeline: upload → transcribe → summarize → save → cleanup."""
    print(f"\nProcessing: {video_path}")
    base_name = os.path.basename(video_path)
    stem = os.path.splitext(base_name)[0]

    # Extract metadata from filename
    meeting_date, meeting_name = extract_metadata_from_filename(base_name)
    if meeting_date:
        print(f"  Detected date: {meeting_date}")
        print(f"  Detected name: {meeting_name}")
    else:
        print("  ⚠ Could not extract date/name from filename")

    try:
        # Upload the file
        print("  Uploading to Gemini...")
        video_file = genai.upload_file(path=video_path)

        # Wait for processing
        print("  Waiting for Gemini to process the video...")
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            print("  ✗ Video processing failed.")
            return

        # ── Pass 1: Transcription ──
        print("  [Pass 1/2] Generating transcript...")
        transcript = transcribe_video(video_file, context)

        transcript_path = os.path.join(TRANSCRIPT_DIR, f"{stem}_transcript.md")
        with open(transcript_path, "w") as f:
            f.write(f"# Transcript: {meeting_name or stem}\n")
            f.write(f"**Date**: {meeting_date or 'Unknown'}\n\n---\n\n")
            f.write(transcript)
        print(f"  Saved transcript to: {transcript_path}")

        # ── Pass 2: Summarization ──
        print("  [Pass 2/2] Generating summary from transcript...")
        summary = summarize_transcript(transcript, context, meeting_date, meeting_name)

        summary_path = os.path.join(OUTPUT_DIR, f"{stem}_summary.md")
        with open(summary_path, "w") as f:
            f.write(summary)
        print(f"  Saved summary to: {summary_path}")

        # Move to processed
        shutil.move(video_path, os.path.join(PROCESSED_DIR, base_name))
        print(f"  Moved video to: {PROCESSED_DIR}/{base_name}")

        # Cleanup remote file
        genai.delete_file(video_file.name)
        print("  ✓ Done")

    except Exception as e:
        print(f"  ✗ Error: {e}")


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Summarize meeting videos using Google Gemini AI (two-pass: transcribe → summarize)"
    )
    parser.add_argument(
        "--context", "-c",
        type=str,
        help="Path to a markdown file with additional context (default: amaze_projects.md if present)",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Disable automatic context loading",
    )
    args = parser.parse_args()

    # Load context: explicit flag > default file > none
    context = None
    if args.no_context:
        print("Context loading disabled.\n")
    elif args.context:
        print(f"Loading context from: {args.context}")
        context = load_context(args.context)
        if context is None:
            print(f"Error: Context file not found: {args.context}")
            exit(1)
    else:
        # Auto-load default context if it exists
        context = load_context(DEFAULT_CONTEXT_FILE)
        if context:
            print(f"Auto-loaded context from: {DEFAULT_CONTEXT_FILE}")
        else:
            print("No context file found (optional).\n")

    # Find media files
    media_files = []
    for ext in SUPPORTED_EXTENSIONS:
        media_files.extend(glob.glob(os.path.join(INPUT_DIR, f"*{ext}")))

    if not media_files:
        print(f"No media files found in '{INPUT_DIR}/' folder.")
        print(f"  Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    print(f"Found {len(media_files)} file(s) to process.\n")

    for video_path in sorted(media_files):
        process_meeting(video_path, context)
        print("-" * 40)

    print("\nAll done!")


if __name__ == "__main__":
    main()

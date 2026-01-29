import os
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

# Model configuration
MODEL = "gemini-flash-latest"

SUMMARY_PROMPT = """Analyze this meeting recording and create a comprehensive, well-structured summary in Markdown format.

## Required Sections:

### 1. Meeting Overview
- Meeting title/topic (infer from context)
- Date and duration (if discernible)
- Participants (list all attendees with their roles if mentioned)

### 2. Executive Summary
A 2-3 paragraph high-level summary of what was discussed and accomplished in this meeting.

### 3. Key Discussion Points
For each major topic discussed:
- **Topic name**: Detailed explanation of what was discussed
- Include context, concerns raised, and conclusions reached

### 4. Decisions Made
List all decisions with:
- The decision itself
- Who made or approved it
- Any conditions or caveats

### 5. Action Items
Create a table with:
| Action Item | Owner | Deadline | Priority |
|-------------|-------|----------|----------|
| Task description | Person responsible | Due date if mentioned | High/Medium/Low |

### 6. Open Questions / Parking Lot
Any unresolved questions or topics deferred for later discussion.

### 7. Next Steps
What happens after this meeting? Any follow-up meetings scheduled?

---
Be thorough and capture nuances. Use bullet points for clarity. If information for a section is not available, note "Not discussed" rather than omitting the section."""

# Create directories if they don't exist
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def summarize_video(video_path, context=None):
    print(f"Processing: {video_path}")

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
            print("  Error: Video processing failed.")
            return

        # Build prompt with optional context
        prompt = SUMMARY_PROMPT
        if context:
            prompt = f"""## Additional Context
The following context has been provided to help with the summary:

{context}

---

{SUMMARY_PROMPT}"""
            print("  Using provided context...")

        print("  Generating summary...")
        model = genai.GenerativeModel(model_name=MODEL)
        response = model.generate_content(
            [video_file, prompt],
            request_options={"timeout": 600}
        )
        
        # Save output as markdown
        base_name = os.path.basename(video_path)
        output_filename = os.path.splitext(base_name)[0] + "_summary.md"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        with open(output_path, "w") as f:
            f.write(response.text)
            
        print(f"  Saved summary to: {output_path}")
        
        # Move to processed
        shutil.move(video_path, os.path.join(PROCESSED_DIR, base_name))
        print(f"  Moved video to: {PROCESSED_DIR}/{base_name}")
        
        # Cleanup remote file
        genai.delete_file(video_file.name)

    except Exception as e:
        print(f"  An error occurred: {e}")

def load_context(context_path):
    """Load context from a markdown file."""
    if not os.path.exists(context_path):
        print(f"Error: Context file not found: {context_path}")
        exit(1)

    with open(context_path, "r") as f:
        return f.read()

def main():
    parser = argparse.ArgumentParser(
        description="Summarize meeting videos using Google Gemini AI"
    )
    parser.add_argument(
        "--context", "-c",
        type=str,
        help="Path to a markdown file with additional context for the summary"
    )
    args = parser.parse_args()

    # Load context if provided
    context = None
    if args.context:
        print(f"Loading context from: {args.context}")
        context = load_context(args.context)

    print("Checking for .mov files in 'input' folder...")
    mov_files = glob.glob(os.path.join(INPUT_DIR, "*.mov"))

    if not mov_files:
        print("No .mov files found in 'input' folder.")
        return

    for video_path in mov_files:
        summarize_video(video_path, context)
        print("-" * 30)

    print("All done!")

if __name__ == "__main__":
    main()

import os
import re
import sys
import glob
import argparse


# ─── Checks ─────────────────────────────────────────────────────────────────────

def check_date(summary_text, expected_date):
    """Check if the summary uses the expected date from the filename."""
    issues = []
    if expected_date and expected_date not in summary_text:
        # Look for what date it actually used
        date_pattern = re.compile(
            r"\*\*Date\*\*:\s*(.+?)(?:\n|$)", re.IGNORECASE
        )
        match = date_pattern.search(summary_text)
        actual = match.group(1).strip() if match else "not found"
        issues.append(
            f"**Date mismatch**: expected `{expected_date}` from filename, "
            f"but summary says `{actual}`"
        )
    return issues


def check_names(summary_text, context_text):
    """Check participant names against the context file's team roster."""
    issues = []
    if not context_text:
        return issues

    # Extract known names from the context table (| **Name** | Role |)
    known_names = set()
    for match in re.finditer(r"\|\s*\*\*(.+?)\*\*", context_text):
        name = match.group(1).strip()
        known_names.add(name)
        # Also add first name only for matching
        first = name.split()[0]
        known_names.add(first)

    # Extract participant names from the summary's overview section
    participants_section = re.search(
        r"\*\*Participants\*\*:?\s*\n((?:\s+[-*].*\n?)+)",
        summary_text,
        re.IGNORECASE,
    )
    if not participants_section:
        return issues

    summary_names = re.findall(
        r"\*\*(.+?)\*\*", participants_section.group(1)
    )

    for name in summary_names:
        first = name.split()[0]
        # Check if name or first name matches any known name (case-insensitive)
        matched = any(
            n.lower() == name.lower() or n.lower() == first.lower()
            for n in known_names
        )
        if not matched:
            # Could be a legitimate new participant — flag as info, not error
            issues.append(
                f"**Unknown participant**: `{name}` not found in context file "
                f"(may be a new attendee or a misspelling)"
            )
        else:
            # Check exact spelling against known names
            exact_match = any(n == name or n == first for n in known_names)
            if not exact_match:
                # Find the closest known name for the suggestion
                for n in known_names:
                    if n.lower() == name.lower() or n.lower() == first.lower():
                        issues.append(
                            f"**Name spelling**: `{name}` should be `{n}` "
                            f"(per context file)"
                        )
                        break

    return issues


def check_sections(summary_text):
    """Check that all 7 required sections are present with correct heading levels."""
    issues = []
    required = [
        "1. Meeting Overview",
        "2. Executive Summary",
        "3. Key Discussion Points",
        "4. Decisions Made",
        "5. Action Items",
        "6. Open Questions",
        "7. Next Steps",
    ]

    for section in required:
        # Allow ## or # heading level, with flexible numbering
        section_name = section.split(". ", 1)[1]
        pattern = re.compile(
            rf"^#+\s*\d*\.?\s*{re.escape(section_name)}",
            re.MULTILINE | re.IGNORECASE,
        )
        if not pattern.search(summary_text):
            issues.append(f"**Missing section**: `{section}` not found")

    # Check for wrong heading levels (### instead of ##)
    wrong_level = re.findall(r"^###\s+\d+\.\s+", summary_text, re.MULTILINE)
    if wrong_level:
        issues.append(
            f"**Heading level**: found {len(wrong_level)} sections using "
            f"`###` instead of `##`"
        )

    return issues


def check_hallucination_markers(summary_text, transcript_text):
    """Flag potential hallucinations by checking summary claims against transcript."""
    issues = []
    if not transcript_text:
        return issues

    # Check for any [unclear] markers that were resolved (potential hallucination)
    unclear_in_transcript = transcript_text.lower().count("[inaudible]")
    if unclear_in_transcript > 0:
        issues.append(
            f"**Inaudible segments**: transcript had {unclear_in_transcript} "
            f"[inaudible] marker(s) — verify these weren't filled in with guesses "
            f"in the summary"
        )

    return issues


# ─── Filename Parser (shared with summarize.py) ────────────────────────────────

def extract_date_from_filename(filename):
    """Extract date from filename pattern YYYY-MM-DD ..."""
    base = os.path.splitext(os.path.basename(filename))[0]
    # Remove _summary suffix
    base = re.sub(r"_summary$", "", base)
    match = re.match(r"(\d{4}-\d{2}-\d{2})", base)
    return match.group(1) if match else None


# ─── Main ───────────────────────────────────────────────────────────────────────

def validate_summary(summary_path, context_text=None, transcript_text=None):
    """Run all validation checks on a single summary file."""
    with open(summary_path, "r") as f:
        summary_text = f.read()

    expected_date = extract_date_from_filename(summary_path)
    all_issues = []

    all_issues.extend(check_date(summary_text, expected_date))
    all_issues.extend(check_names(summary_text, context_text))
    all_issues.extend(check_sections(summary_text))
    all_issues.extend(check_hallucination_markers(summary_text, transcript_text))

    return all_issues


def main():
    parser = argparse.ArgumentParser(
        description="Validate meeting summary files for accuracy and completeness"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Summary files to validate (default: all .md files in output/)",
    )
    parser.add_argument(
        "--context", "-c",
        type=str,
        default="amaze_projects.md",
        help="Path to context file for name checking (default: amaze_projects.md)",
    )
    parser.add_argument(
        "--transcripts", "-t",
        type=str,
        default="transcripts",
        help="Path to transcripts directory (default: transcripts/)",
    )
    args = parser.parse_args()

    # Load context
    context_text = None
    if os.path.exists(args.context):
        with open(args.context, "r") as f:
            context_text = f.read()

    # Determine files to validate
    if args.files:
        files = args.files
    else:
        files = sorted(glob.glob(os.path.join("output", "*.md")))

    if not files:
        print("No summary files found to validate.")
        return

    total_issues = 0
    for filepath in files:
        basename = os.path.basename(filepath)

        # Try to find matching transcript
        transcript_text = None
        stem = os.path.splitext(basename)[0].replace("_summary", "")
        transcript_path = os.path.join(
            args.transcripts, f"{stem}_transcript.md"
        )
        if os.path.exists(transcript_path):
            with open(transcript_path, "r") as f:
                transcript_text = f.read()

        issues = validate_summary(filepath, context_text, transcript_text)

        if issues:
            print(f"\n⚠  {basename}  ({len(issues)} issue(s))")
            for issue in issues:
                print(f"   • {issue}")
            total_issues += len(issues)
        else:
            print(f"✓  {basename}")

    print(f"\n{'─' * 40}")
    print(f"Validated {len(files)} file(s), found {total_issues} issue(s).")

    if total_issues > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

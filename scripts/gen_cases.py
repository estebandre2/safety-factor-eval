"""Generate data/cases.jsonl and data/cases_review.md."""
from pathlib import Path

from sfe.cases import generate_cases, write_cases

if __name__ == "__main__":
    cases = generate_cases(2026)
    write_cases(cases, Path("data/cases.jsonl"), Path("data/cases_review.md"))
    print(f"wrote {len(cases)} cases")

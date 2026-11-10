"""Render writeup/safety-factor.md to writeup/safety-factor.pdf (Markdown -> HTML -> headless Chrome)."""
import subprocess
import sys
from pathlib import Path

import markdown

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
src, html, pdf = Path("writeup/safety-factor.md"), Path("writeup/safety-factor.html"), Path("writeup/safety-factor.pdf")
body = markdown.markdown(src.read_text(), extensions=["tables", "sane_lists"])
css = """body{font-family:Georgia,serif;font-size:10pt;line-height:1.4;max-width:46em;margin:auto;color:#111}
h1{font-size:18pt}h2{font-size:13.5pt;margin-top:1.4em}h3{font-size:11.5pt}
table{border-collapse:collapse;font-size:9pt;margin:.6em 0}th,td{border:1px solid #bbb;padding:3px 6px;vertical-align:top}
th{background:#f2f2f2}img{max-width:66%;display:block;margin:auto}code{font-size:9pt}blockquote{color:#555;border-left:3px solid #ccc;margin-left:0;padding-left:1em}
@page{size:Letter;margin:15mm}"""
html.write_text(f"<!doctype html><meta charset='utf-8'><title>Safety Factor</title><style>{css}</style>{body}")
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf.resolve()}", html.resolve().as_uri()], check=True, capture_output=True)
html.unlink()
print(pdf, pdf.stat().st_size, "bytes", file=sys.stderr)

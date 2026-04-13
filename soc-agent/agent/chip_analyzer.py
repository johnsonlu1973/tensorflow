"""
Chip Analyzer
Reads uploaded chip spec files and produces a structured comparison.
Supports: PDF text extraction, .txt, .json files.
"""
import json
import os
import re
from pathlib import Path

import anthropic


class ChipAnalyzer:
    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.specs_dir = Path(__file__).parent.parent / "data" / "chip_specs"

    def load_specs(self) -> dict:
        """Read all spec files and return combined text."""
        specs: dict[str, str] = {}
        for f in self.specs_dir.iterdir():
            if f.suffix.lower() in {".txt", ".json", ".md"} and f.name != "README.md":
                specs[f.name] = f.read_text(encoding="utf-8", errors="ignore")
            elif f.suffix.lower() == ".pdf":
                text = self._extract_pdf(f)
                if text:
                    specs[f.name] = text
        return specs

    def analyze(self, use_cases: list[str]) -> dict:
        """Check whether current Qualcomm/MediaTek chips satisfy the given use cases."""
        specs = self.load_specs()
        if not specs:
            return {
                "qualcomm": {"satisfies": [], "gaps": use_cases, "note": "No spec files uploaded yet."},
                "mediatek": {"satisfies": [], "gaps": use_cases, "note": "No spec files uploaded yet."},
            }

        specs_text = "\n\n".join(f"=== {name} ===\n{content}" for name, content in specs.items())
        prompt = f"""You are a chip architect at a SOC company.
Analyze whether current Qualcomm and MediaTek flagship chips can satisfy these use cases:

{json.dumps(use_cases, ensure_ascii=False, indent=2)}

Chip specifications available:
{specs_text}

Return ONLY valid JSON:
{{
  "qualcomm": {{
    "chip_model": "e.g. Snapdragon 8 Elite",
    "satisfies": ["use case description"],
    "partially_satisfies": [{{"use_case": "", "limitation": ""}}],
    "gaps": ["use cases that cannot be satisfied"]
  }},
  "mediatek": {{
    "chip_model": "e.g. Dimensity 9400",
    "satisfies": ["use case description"],
    "partially_satisfies": [{{"use_case": "", "limitation": ""}}],
    "gaps": ["use cases that cannot be satisfied"]
  }},
  "summary": "overall assessment"
}}"""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"Chip analysis error: {e}")
        return {"qualcomm": {"satisfies": [], "gaps": []}, "mediatek": {"satisfies": [], "gaps": []}}

    def _extract_pdf(self, path: Path) -> str:
        """Best-effort PDF text extraction without heavy deps."""
        try:
            import subprocess
            result = subprocess.run(
                ["pdftotext", str(path), "-"],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout
        except Exception:
            return ""

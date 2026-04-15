"""
Chip Analyzer
Reads structured chip spec JSON files and evaluates whether
current Qualcomm / MediaTek flagships can satisfy identified use cases.
Also supports PDF / TXT uploads via best-effort text extraction.
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

    # ------------------------------------------------------------------
    def load_specs(self) -> list[dict]:
        """Load all chip spec JSON files; ignore README / gitkeep."""
        specs: list[dict] = []
        for f in sorted(self.specs_dir.glob("*.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                # Support both single-chip and multi-chip comparison files
                if "chips" in data:
                    specs.extend(data["chips"])
                elif "brand" in data:
                    specs.append(data)
            except Exception as e:
                print(f"  Could not read {f.name}: {e}")
        # Fallback: also read plain text / pdf files
        for f in self.specs_dir.iterdir():
            if f.suffix.lower() in {".txt", ".md"} and f.name != "README.md":
                specs.append({"brand": "uploaded", "model": f.stem,
                               "raw_text": f.read_text(encoding="utf-8", errors="ignore")})
            elif f.suffix.lower() == ".pdf":
                text = self._extract_pdf(f)
                if text:
                    specs.append({"brand": "uploaded", "model": f.stem, "raw_text": text})
        return specs

    def load_comparison(self) -> dict | None:
        """Load the latest comparison file (has 'comparison' key)."""
        for f in sorted(self.specs_dir.glob("*.json"), reverse=True):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                if "comparison" in data:
                    return data
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    def analyze(self, use_cases: list[str]) -> dict:
        """
        For each use case determine:
          qualcomm_status / mediatek_status: "yes" | "partial" | "no"
        Returns structured JSON for report_generator consumption.
        """
        specs = self.load_specs()
        comparison = self.load_comparison()

        if not specs:
            return self._no_spec_result(use_cases)

        specs_json = json.dumps(specs, ensure_ascii=False, indent=2)[:8000]
        cmp_json = (
            json.dumps(comparison.get("comparison", {}), ensure_ascii=False, indent=2)
            if comparison else "{}"
        )

        prompt = f"""You are a chip architect at a leading SOC company.
Evaluate whether the following use cases can be satisfied by current flagship chips.

Use Cases:
{json.dumps(use_cases, ensure_ascii=False, indent=2)}

Chip Specifications:
{specs_json}

Comparison Summary:
{cmp_json}

Return ONLY valid JSON:
{{
  "evaluations": [
    {{
      "use_case": "use case title",
      "qualcomm_model": "Snapdragon 8 Elite Gen 2",
      "qualcomm_status": "yes|partial|no",
      "qualcomm_reason": "brief explanation",
      "mediatek_model": "Dimensity 9500",
      "mediatek_status": "yes|partial|no",
      "mediatek_reason": "brief explanation",
      "gap_notes": "what is missing if either chip cannot fully satisfy"
    }}
  ],
  "overall_gaps": ["gaps not satisfiable by either chip"],
  "qualcomm_unique_strengths": ["..."],
  "mediatek_unique_strengths": ["..."],
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
            # debug 
            print(f"[Chip] stop_reason: {resp.stop_reason}")        # ← 加這行
            print(f"[Chip] response length: {len(text)}")           # ← 加這行
            print(f"[Chip] response tail:\n{text[-200:]}")          # ← 加這行

        return self._no_spec_result(use_cases)

    def get_known_gaps(self) -> list[str]:
        """Return pre-defined strategic gaps from the comparison file."""
        cmp = self.load_comparison()
        if cmp:
            return cmp.get("comparison", {}).get("key_gaps_for_soc_strategy", [])
        return []

    def get_chip_summary(self) -> dict:
        """Return a concise chip capability summary for report headers."""
        specs = self.load_specs()
        out: dict[str, dict] = {}
        for chip in specs:
            brand = chip.get("brand", "").lower()
            if brand in {"qualcomm", "mediatek"}:
                npu = chip.get("npu", {})
                out[brand] = {
                    "model": chip.get("model", ""),
                    "tops": npu.get("tops", "N/A"),
                    "strengths": chip.get("strengths", []),
                }
        return out

    # ------------------------------------------------------------------
    def _no_spec_result(self, use_cases: list[str]) -> dict:
        return {
            "evaluations": [
                {
                    "use_case": uc,
                    "qualcomm_model": "Snapdragon 8 Elite Gen 2",
                    "qualcomm_status": "unknown",
                    "qualcomm_reason": "No spec file loaded",
                    "mediatek_model": "Dimensity 9500",
                    "mediatek_status": "unknown",
                    "mediatek_reason": "No spec file loaded",
                    "gap_notes": "",
                }
                for uc in use_cases
            ],
            "overall_gaps": use_cases,
            "summary": "Chip spec files not loaded.",
        }

    def _extract_pdf(self, path: Path) -> str:
        """Best-effort PDF text extraction without heavy deps."""
        try:
            import subprocess
            result = subprocess.run(
                ["pdftotext", str(path), "-"],
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout
        except Exception:
            return ""

"""
Feedback Processor
Reads GitHub Issues labelled 'soc-feedback', extracts insights,
and writes new skills to skills/learned_skills.json.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import requests


class FeedbackProcessor:
    def __init__(self, config: dict):
        self.config = config
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.gh_token = os.environ.get("GITHUB_TOKEN", "")
        self.gh_repo = os.environ.get(
            "GITHUB_REPOSITORY",
            f"{config['github']['owner']}/{config['github']['repo']}",
        )
        self.label = config["github"]["feedback_label"]
        self.skills_path = (
            Path(__file__).parent.parent / "skills" / "learned_skills.json"
        )

    # ------------------------------------------------------------------
    def process_github_issues(self) -> list[dict]:
        issues = self._fetch_feedback_issues()
        if not issues:
            print("No new feedback issues found.")
            return []

        skills_db = self._load_skills()
        processed_ids = set(skills_db.get("processed_feedback_issues", []))
        new_issues = [i for i in issues if i["number"] not in processed_ids]

        if not new_issues:
            print("All feedback issues already processed.")
            return []

        new_skills = []
        for issue in new_issues:
            skill = self._extract_skill(issue)
            if skill:
                new_skills.append(skill)
                processed_ids.add(issue["number"])

        skills_db["skills"].extend(new_skills)
        skills_db["processed_feedback_issues"] = list(processed_ids)
        skills_db["last_updated"] = datetime.now(timezone.utc).isoformat()
        skills_db["skill_stats"]["total_skills"] = len(skills_db["skills"])
        self._save_skills(skills_db)
        print(f"Added {len(new_skills)} new skills from {len(new_issues)} issues.")
        return new_skills

    # ------------------------------------------------------------------
    def _fetch_feedback_issues(self) -> list[dict]:
        if not self.gh_token:
            return []
        url = f"https://api.github.com/repos/{self.gh_repo}/issues"
        headers = {
            "Authorization": f"token {self.gh_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        params = {"labels": self.label, "state": "open", "per_page": 50}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Failed to fetch issues: {e}")
            return []

    def _extract_skill(self, issue: dict) -> dict | None:
        body = issue.get("body", "") or ""
        title = issue.get("title", "") or ""
        prompt = f"""You are a learning system for a SOC strategy analysis agent.
A user submitted the following feedback via GitHub Issue:

Title: {title}
Body: {body}

Extract a reusable analysis skill or instruction that should improve future reports.
Return ONLY valid JSON:
{{
  "name": "short skill name (English)",
  "description": "what this skill does",
  "trigger": ["keyword1", "keyword2"],
  "prompt_addition": "exact instruction to add to future prompts",
  "confidence": 0.9
}}
If no clear skill can be extracted, return null."""
        try:
            resp = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            if text.lower() == "null" or not text.startswith("{"):
                return None
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return None
            skill = json.loads(m.group())
            skill["id"] = f"skill-{issue['number']:04d}"
            skill["learned_from_issue"] = issue["number"]
            skill["created_at"] = datetime.now(timezone.utc).isoformat()
            skill["usage_count"] = 0
            return skill
        except Exception as e:
            print(f"Skill extraction failed for issue #{issue.get('number')}: {e}")
            return None

    def _load_skills(self) -> dict:
        if self.skills_path.exists():
            with open(self.skills_path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "version": "1.0.0",
            "last_updated": "",
            "skills": [],
            "processed_feedback_issues": [],
            "skill_stats": {"total_skills": 0, "total_applications": 0},
        }

    def _save_skills(self, data: dict):
        self.skills_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.skills_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

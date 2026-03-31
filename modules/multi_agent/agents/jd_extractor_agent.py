from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound

from modules.core.config.settings import create_llm, logger

from ..base import BaseAgent
from ..models import AgentResult


class JDExtractorAgent(BaseAgent):
    name = "jd_extractor"

    def __init__(self) -> None:
        self.llm = create_llm(temperature=0)

    def _first_url(self, text: str) -> str | None:
        match = re.search(r"https?://[^\s)]+", text)
        return match.group(0).strip() if match else None

    def _is_noise_chunk(self, chunk: str) -> bool:
        lowered = chunk.lower()
        noise_markers = [
            "themeoptions",
            "vartheme",
            "tab-indicator",
            "button-primary",
            "font-family",
            "pcsx-",
            "woff",
            "navbar-",
            "customfonts",
        ]
        if any(marker in lowered for marker in noise_markers):
            return True

        if chunk.count("{") + chunk.count("}") >= 2:
            return True
        if chunk.count('":') >= 2:
            return True
        if chunk.count("#") >= 3:
            return True

        # Drop chunks that look like CSS/JSON config payloads.
        alpha = sum(ch.isalpha() for ch in chunk)
        ratio = alpha / max(len(chunk), 1)
        if ratio < 0.45 and len(chunk) > 40:
            return True

        return False

    def _sanitize_text_for_jd(self, text: str) -> str:
        cleaned = text or ""
        cleaned = re.sub(
            r"themeoptions.*?(responsibilities|qualifications|requirements|overview|about\s+the\s+role)",
            r" \1",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(r'"[A-Za-z0-9_\-]+"\s*:\s*"[^"]{0,180}"', " ", cleaned)
        cleaned = re.sub(r"\{[^{}]{0,500}\}", " ", cleaned)
        cleaned = cleaned.replace("{", " ").replace("}", " ").replace('"', " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        segments = re.split(r"(?<=[\.\!\?])\s+", cleaned)
        kept: List[str] = []
        for segment in segments:
            s = segment.strip()
            if not s:
                continue
            if self._is_noise_chunk(s) and not re.search(
                r"responsibil|qualif|requirement|about\s+the\s+role|overview",
                s,
                re.IGNORECASE,
            ):
                continue
            kept.append(s)

        return " ".join(kept).strip()

    def _extract_structured_jobposting(self, html_text: str, url: str) -> Dict[str, Any] | None:
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            scripts = soup.find_all("script", {"type": "application/ld+json"})
            for script in scripts:
                raw = (script.string or script.get_text() or "").strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except Exception:
                    continue

                candidates: List[Dict[str, Any]] = []
                if isinstance(data, dict):
                    candidates = [data]
                elif isinstance(data, list):
                    candidates = [item for item in data if isinstance(item, dict)]

                for item in candidates:
                    if str(item.get("@type") or "").lower() != "jobposting":
                        continue

                    title = str(item.get("title") or "Software Engineer").strip()
                    description = self._sanitize_text_for_jd(str(item.get("description") or ""))
                    if not description:
                        continue

                    qualifications = ""
                    match = re.search(
                        r"(required qualifications:.*?)(preferred qualifications:|other requirements:|$)",
                        description,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if match:
                        qualifications = match.group(1).strip()

                    job = self._heuristic_extract(description)
                    job["title"] = title
                    job["description"] = description[:2200]
                    job["qualifications"] = qualifications[:1200]
                    return job
        except Exception as exc:
            logger.warning("Structured JobPosting extraction skipped due to parse issue: %s", exc)
        return None

    async def _fetch_url_text(self, url: str) -> str:
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 AutoApplyAgent/1.0"})
            response.raise_for_status()

        try:
            soup = BeautifulSoup(response.text, "lxml")
        except FeatureNotFound:
            logger.warning("lxml parser not available. Falling back to html.parser for JD extraction.")
            soup = BeautifulSoup(response.text, "html.parser")

        # Remove noisy sections before extracting visible text
        for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
            tag.decompose()

        title = (soup.title.string or "").strip() if soup.title else ""
        heading = ""
        h1 = soup.find("h1")
        if h1:
            heading = " ".join(h1.get_text(" ", strip=True).split())

        filtered_chunks: List[str] = []
        seen: set[str] = set()
        for raw_chunk in soup.stripped_strings:
            chunk = " ".join(str(raw_chunk).split())
            if not chunk:
                continue
            if len(chunk) < 20 and "responsibil" not in chunk.lower() and "qualif" not in chunk.lower():
                continue
            if self._is_noise_chunk(chunk):
                continue
            if chunk in seen:
                continue
            seen.add(chunk)
            filtered_chunks.append(chunk)

        combined = "\n".join(part for part in [title, heading, *filtered_chunks] if part).strip()
        combined = self._sanitize_text_for_jd(combined)

        # Keep token footprint bounded for LLM extraction
        return combined[:12000]

    def _heuristic_extract(self, raw_text: str) -> Dict[str, Any]:
        normalized = raw_text or ""
        lowered = normalized.lower()

        title = "Software Engineer"
        title_patterns = [
            r"\b(role|position|title)\s*[:\-]\s*([^\n\.]{3,80})",
            r"\b(hiring|looking for)\s+(a|an)?\s*([^\n\.]{3,80})",
        ]
        for pattern in title_patterns:
            match = re.search(pattern, lowered, re.IGNORECASE)
            if match:
                candidate = match.group(match.lastindex or 1).strip()
                if candidate:
                    title = candidate.title()
                    break

        skill_candidates = [
            "c#", ".net", "azure", "react", "angular", "javascript", "typescript",
            "python", "sql", "ci/cd", "devops", "llm", "prompt engineering", "fastapi",
        ]
        skills: List[str] = []
        for skill in skill_candidates:
            if skill in lowered:
                skills.append(skill.upper() if skill in {"c#", ".net", "llm", "ci/cd"} else skill.title())

        description = normalized[:2200].strip()

        return {
            "title": title,
            "description": description,
            "qualifications": "",
            "skills_required": skills,
        }

    async def _llm_extract(self, raw_text: str) -> Dict[str, Any]:
        prompt = f"""
Extract a structured Job Description from the text below.
Return valid JSON ONLY with this exact schema:
{{
  "title": "string",
  "description": "string",
  "qualifications": "string",
  "skills_required": ["skill1", "skill2"]
}}

Rules:
- Do not invent facts. Use only provided text.
- Keep title concise.
- Keep description <= 1200 characters.
- Keep qualifications <= 800 characters.
- Return 6-12 most relevant skills.

TEXT:
{raw_text[:12000]}
"""
        response = await self.llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        cleaned = content.strip().replace("```json", "").replace("```", "")
        data = json.loads(cleaned)

        title = str(data.get("title") or "Software Engineer").strip()
        description = str(data.get("description") or "").strip()
        qualifications = str(data.get("qualifications") or "").strip()

        raw_skills = data.get("skills_required") or []
        if isinstance(raw_skills, str):
            skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        elif isinstance(raw_skills, list):
            skills = [str(s).strip() for s in raw_skills if str(s).strip()]
        else:
            skills = []

        return {
            "title": title,
            "description": description,
            "qualifications": qualifications,
            "skills_required": skills,
        }

    async def execute(self, payload: Dict[str, Any]) -> AgentResult:
        query = str(payload.get("query") or "").strip()
        jd_text = str(payload.get("jd_text") or "").strip()
        jd_url = str(payload.get("jd_url") or "").strip()

        inferred_url = self._first_url(query) if query else None
        target_url = jd_url or inferred_url

        raw_text = ""
        source = "query"

        try:
            if target_url:
                timeout = httpx.Timeout(20.0, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    response = await client.get(target_url, headers={"User-Agent": "Mozilla/5.0 AutoApplyAgent/1.0"})
                    response.raise_for_status()

                structured_job = self._extract_structured_jobposting(response.text, target_url)
                if structured_job:
                    return AgentResult(
                        agent=self.name,
                        success=True,
                        data={
                            "job": structured_job,
                            "source": "url_structured",
                            "url": target_url,
                        },
                    )

                # Fallback: extract from visible page text when structured data isn't available.
                raw_text = await self._fetch_url_text(target_url)
                source = "url"
            elif jd_text:
                raw_text = jd_text
                source = "jd_text"
            else:
                raw_text = query
                source = "query"

            if not raw_text.strip():
                return AgentResult(
                    agent=self.name,
                    success=False,
                    error="No JD content found. Provide JD text or a job URL.",
                )

            raw_text = self._sanitize_text_for_jd(raw_text)

            try:
                job = await self._llm_extract(raw_text)
            except Exception as exc:
                logger.warning("JDExtractorAgent LLM parse failed, using heuristic fallback: %s", exc)
                job = self._heuristic_extract(raw_text)

            return AgentResult(
                agent=self.name,
                success=True,
                data={
                    "job": job,
                    "source": source,
                    "url": target_url or "",
                },
            )
        except Exception as exc:
            logger.exception("JD extraction failed")
            return AgentResult(agent=self.name, success=False, error=str(exc))


import logging
import asyncio
import subprocess
import json
import re
from datetime import datetime
from typing import Any, Dict, List

from modules.core.config.settings import config, create_llm
from modules.core.profile.human_loop import PersonalProfile

logger = logging.getLogger(__name__)


class CVEngine:

    def __init__(self):

        self.llm = create_llm(temperature=0.2)

    # ---------------------------------------------------
    # Escape LaTeX special characters
    # ---------------------------------------------------

    def escape_latex(self, text: str):

        replacements = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
        }

        for k, v in replacements.items():
            text = text.replace(k, v)

        return text

    # ---------------------------------------------------
    # Load LaTeX template
    # ---------------------------------------------------

    def load_template(self):

        template_path = config.TEMPLATES_DIR / "cv_template.tex"

        with open(template_path, "r") as f:
            return f.read()

    # ---------------------------------------------------
    # Generate structured projects using JSON
    # ---------------------------------------------------

    def _collect_profile_projects(self, profile: PersonalProfile) -> List[Dict[str, str]]:
        projects: List[Dict[str, str]] = []
        for index in range(1, 7):
            name = getattr(profile, f"project_{index}_name", None)
            if not name:
                continue

            projects.append(
                {
                    "name": str(name).strip(),
                    "tech": str(getattr(profile, f"project_{index}_tech_stack", "") or "").strip(),
                    "year": str(getattr(profile, f"project_{index}_duration", "") or "").strip(),
                    "description": str(getattr(profile, f"project_{index}_description", "") or "").strip(),
                }
            )

        return projects

    def _extract_jd_keywords(self, job_data: Dict[str, Any]) -> set[str]:
        parts: List[str] = []
        for key in ["title", "description", "qualifications"]:
            value = job_data.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)

        skills = job_data.get("skills_required")
        if isinstance(skills, list):
            parts.extend(str(item) for item in skills if str(item).strip())
        elif isinstance(skills, str) and skills.strip():
            parts.append(skills)

        text = " ".join(parts).lower()
        tokens = re.findall(r"[a-z0-9\+#\.]{2,}", text)
        stop_words = {
            "and", "the", "with", "for", "that", "this", "from", "into", "using",
            "have", "has", "are", "you", "our", "your", "will", "job", "role",
            "required", "preferred", "ability", "experience", "skills", "work", "team",
            "strong", "high", "level", "including", "across", "within", "their",
        }
        return {token for token in tokens if token not in stop_words}

    def _rank_projects_by_jd(self, profile: PersonalProfile, job_data: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
        projects = self._collect_profile_projects(profile)
        if not projects:
            return []

        jd_keywords = self._extract_jd_keywords(job_data)
        scored: List[tuple[int, Dict[str, str]]] = []

        for project in projects:
            project_text = f"{project['name']} {project['tech']} {project['description']}".lower()
            project_tokens = set(re.findall(r"[a-z0-9\+#\.]{2,}", project_text))
            overlap = len(jd_keywords & project_tokens)

            # Small boost for explicit cloud/stack matches
            bonus = 0
            for marker in ["azure", "aws", "react", "angular", "sql", "c#", ".net", "llm", "agent", "fastapi"]:
                if marker in project_text and marker in jd_keywords:
                    bonus += 2

            scored.append((overlap + bonus, project))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [item[1] for item in scored[: max(1, min(limit, len(scored)))]]

        normalized: List[Dict[str, Any]] = []
        for project in selected:
            bullets = [
                project["description"] or "Delivered an end-to-end project aligned to target job requirements.",
                f"Tech stack: {project['tech']}" if project["tech"] else "Implemented production-focused engineering practices.",
            ]
            normalized.append(
                {
                    "name": project["name"],
                    "tech": project["tech"],
                    "year": project["year"],
                    "bullets": bullets,
                }
            )

        return normalized

    async def generate_projects(self, job_data, profile):
        ranked_fallback = self._rank_projects_by_jd(profile, job_data, limit=3)
        target_count = min(3, len(ranked_fallback)) if ranked_fallback else 1

        prompt = f"""
Return valid JSON ONLY.

NOTE:
- Strictly return exactly {target_count} project entries in JSON.
- Strictly don't change the project name.
- Select projects from the profile that best match the job requirements. Focus on projects that utilize the skills required by the job. For each project, provide a brief description, the tech stack used, and the year it was completed.
- add 2 bullet points for each project highlighting the key achievements or responsibilities, especially those that align with the job requirements.
- Bullet points shouldn't be short. They should be descriptive enough to convey the impact and relevance of the project to the job.
- strictly limit bullet points to not more than 2 lines each.


JSON FORMAT:

{{
 "projects":[
   {{
     "name":"project name",
     "tech":"tech stack",
     "year":"duration",
     "bullets":[
       "bullet 1",
       "bullet 2"
     ]
   }}
 ]
}}

JOB SKILLS:
{job_data.get("skills_required")}

JOB TITLE:
{job_data.get("title")}

JOB DESCRIPTION:
{job_data.get("description")}

JOB QUALIFICATIONS:
{job_data.get("qualifications")}

PROJECT DATABASE

1.
Name: {profile.project_1_name}
Tech: {profile.project_1_tech_stack}
Description: {profile.project_1_description}
Duration: {profile.project_1_duration}

2.
Name: {profile.project_2_name}
Tech: {profile.project_2_tech_stack}
Description: {profile.project_2_description}
Duration: {profile.project_2_duration}

3.
Name: {profile.project_3_name}
Tech: {profile.project_3_tech_stack}
Description: {profile.project_3_description}
Duration: {profile.project_3_duration}

4.
Name: {profile.project_4_name}
Tech: {profile.project_4_tech_stack}
Description: {profile.project_4_description}
Duration: {profile.project_4_duration}

5.
Name: {profile.project_5_name}
Tech: {profile.project_5_tech_stack}
Description: {profile.project_5_description}
Duration: {profile.project_5_duration}

6.
Name: {profile.project_6_name}
Tech: {profile.project_6_tech_stack}
Description: {profile.project_6_description}
Duration: {profile.project_6_duration}
"""

        response = await self.llm.ainvoke(prompt)

        try:
            content = response.content.strip()
            content = content.replace("```json", "").replace("```", "")
            data = json.loads(content)
        except Exception:
            logger.warning("LLM JSON parsing failed, using deterministic JD-ranked fallback projects")
            return ranked_fallback

        parsed_projects = data.get("projects") if isinstance(data, dict) else []
        if not isinstance(parsed_projects, list):
            parsed_projects = []

        normalized: List[Dict[str, Any]] = []
        for item in parsed_projects:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()
            if not name:
                continue

            tech = str(item.get("tech") or "").strip()
            year = str(item.get("year") or "").strip()
            bullets_raw = item.get("bullets")

            if isinstance(bullets_raw, list):
                bullets = [str(b).strip() for b in bullets_raw if str(b).strip()]
            elif isinstance(bullets_raw, str) and bullets_raw.strip():
                bullets = [bullets_raw.strip()]
            else:
                bullets = []

            if len(bullets) < 2:
                fallback_project = next((p for p in ranked_fallback if p.get("name") == name), None)
                if fallback_project:
                    fallback_bullets = fallback_project.get("bullets", [])
                    for bullet in fallback_bullets:
                        if bullet and bullet not in bullets:
                            bullets.append(bullet)
                        if len(bullets) >= 2:
                            break

            if len(bullets) < 2:
                bullets.append("Delivered measurable impact through robust engineering and production-quality implementation.")
            if len(bullets) < 2:
                bullets.append("Collaborated across design, development, and testing to ensure reliable outcomes.")

            normalized.append(
                {
                    "name": name,
                    "tech": tech,
                    "year": year,
                    "bullets": bullets[:2],
                }
            )

        if len(normalized) < target_count:
            existing_names = {item["name"] for item in normalized}
            for project in ranked_fallback:
                if project["name"] in existing_names:
                    continue
                normalized.append(project)
                existing_names.add(project["name"])
                if len(normalized) >= target_count:
                    break

        return normalized[:target_count] if normalized else ranked_fallback

    # ---------------------------------------------------
    # Rewrite Experience Bullets Based on JD
    # ---------------------------------------------------

    async def tailor_experience(self, job_data):

        prompt = f"""
Rewrite the following experience bullet points to align with the job description.

IMPORTANT RULES:
- Do NOT change company, role, or duration
- Keep the original meaning
- Expand bullets slightly to show impact
- Highlight relevant job skills using \\textbf{{}}
- Each bullet should be strong and ATS-optimized
- add 3 bullet points for each experience highlighting the key achievements or responsibilities, especially those that align with the job requirements.
- Bullet points shouldn't be short. They should be descriptive enough to convey the impact and relevance of the experience to the job.
- Return ONLY LaTeX item lists

FORMAT EXACTLY:

\\resumeItemListStart
\\item bullet
\\item bullet
\\resumeItemListEnd

JOB DESCRIPTION SKILLS:
{job_data.get("skills_required")}

EXPERIENCE DATA

INFOSYS:
1. Completed advanced training in Agentic AI systems using LangChain, LangGraph, MCP and A2A frameworks.
2. Built multi-agent workflows and RAG pipelines for document processing and knowledge retrieval.
3. Developed backend APIs using FastAPI to support scalable AI-driven applications.
4. Integrated Langfuse observability and Guardrails to monitor and validate LLM responses.

ANNAM.AI:
1. Built deep learning models to identify plant species and estimate growth stages from images.
2. Used computer vision techniques for plant health monitoring and feature extraction.

EASECRUIT:
1. Developed a resume parser using Node.js and React converting resumes into structured JSON.
2. Integrated LLMs to extract GitHub links, repositories and candidate metadata.
3. Optimized backend pipeline to process 100+ resumes in under 15 seconds.

Return valid JSON ONLY.

{{
 "infosys":"latex bullets",
 "annam":"latex bullets",
 "easecruit":"latex bullets"
}}
"""

        response = await self.llm.ainvoke(prompt)

        try:
            content = response.content.strip()
            content = content.replace("```json", "").replace("```", "")
            data = json.loads(response.content)
        except Exception:
            logger.warning("Experience rewrite failed")

            data = {
                "infosys": "",
                "annam": "",
                "easecruit": ""
            }

        return data

    # ---------------------------------------------------
    # Convert project JSON → LaTeX
    # ---------------------------------------------------

    def build_projects_latex(self, projects):

        latex = "\\resumeSubHeadingListStart\n"

        for p in projects:

            name = self.escape_latex(p["name"])
            tech = self.escape_latex(p["tech"])
            year = self.escape_latex(p["year"])

            latex += f"""
\\resumeProject
{{{name}}}
{{\\textbf{{{tech}}}}}
{{{year}}}
{{}}

\\resumeItemListStart
"""

            for bullet in p["bullets"]:
                bullet = self.escape_latex(bullet)
                latex += f"\\item {bullet}\n"

            latex += "\\resumeItemListEnd\n"

        latex += "\\resumeSubHeadingListEnd\n"

        return latex

    # ---------------------------------------------------
    # Generate Skills
    # ---------------------------------------------------

    def generate_skills(self, profile):

        items = []

        if profile.programming_languages:
            items.append(f"\\item \\textbf{{Programming:}} {profile.programming_languages}")

        items.append("\\item \\textbf{Agentic AI / Gen. AI:} LangChain, LangGraph, MCP, A2A, RAG, Guardrails, Langfuse")

        if profile.frameworks:
            items.append(f"\\item \\textbf{{Frameworks:}} {profile.frameworks}")

        items.append("\\item \\textbf{Machine Learning:} TensorFlow, PyTorch, Keras, OpenCV")

        if profile.tools:
            items.append(f"\\item \\textbf{{Tools:}} {profile.tools}")

        skills = "\n".join(items)

        return f"""
\\begin{{itemize}}[leftmargin=*, noitemsep]
{skills}
\\end{{itemize}}
"""

    # ---------------------------------------------------
    # Build CV
    # ---------------------------------------------------

    def build_cv(self, template, projects_latex, skills, experience):

        latex = template.replace("{{PROJECTS}}", projects_latex)
        latex = latex.replace("{{SKILLS}}", skills)

        latex = latex.replace("{{INFOSYS_EXPERIENCE}}", experience["infosys"])
        latex = latex.replace("{{ANNAM_EXPERIENCE}}", experience["annam"])
        latex = latex.replace("{{EASECRUIT_EXPERIENCE}}", experience["easecruit"])

        return latex

    # ---------------------------------------------------
    # Compile LaTeX
    # ---------------------------------------------------

    def compile_pdf(self, latex_code):

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        tex_file = config.OUTPUT_DIR / f"cv_{timestamp}.tex"

        with open(tex_file, "w") as f:
            f.write(latex_code)

        proc = subprocess.run(
            [
            "pdflatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory",
            str(config.OUTPUT_DIR),
            str(tex_file),
            ],
            capture_output=True,
            text=True,
        )

        pdf_file = config.OUTPUT_DIR / f"cv_{timestamp}.pdf"
        if proc.returncode != 0 or not pdf_file.exists():
            logger.error("pdflatex failed for %s", tex_file)
            if proc.stdout:
                logger.error("pdflatex stdout:\n%s", proc.stdout[-2000:])
            if proc.stderr:
                logger.error("pdflatex stderr:\n%s", proc.stderr[-2000:])
            raise RuntimeError(
                f"Failed to compile resume PDF. Check LaTeX/template syntax and installed TeX packages. Source: {tex_file}"
            )

        # remove unwanted files
        extensions = [".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"]

        for ext in extensions:
            file = config.OUTPUT_DIR / f"cv_{timestamp}{ext}"
            if file.exists():
                file.unlink()

        return pdf_file

    # ---------------------------------------------------
    # Main Pipeline
    # ---------------------------------------------------

    async def generate_cv_for_job(self, job_data: Dict):

        profile = PersonalProfile.load_from_file()

        template = self.load_template()

        projects_json = await self.generate_projects(job_data, profile)

        projects_latex = self.build_projects_latex(projects_json)

        experience = await self.tailor_experience(job_data)

        skills = self.generate_skills(profile)

        latex = self.build_cv(template, projects_latex, skills, experience)

        pdf = self.compile_pdf(latex)

        return pdf


# ---------------------------------------------------
# Test
# ---------------------------------------------------

async def test():

    job_data = {
        "title": "Software Engineer",
        "skills_required": [
            "C++",
            "Data Structure",
            "FastAPI",
            "Algorithm"
        ],
    }

    engine = CVEngine()

    pdf = await engine.generate_cv_for_job(job_data)

    print("Generated CV:", pdf)


if __name__ == "__main__":
    asyncio.run(test())





# """
# CV Engine Module
# Generates tailored CVs using LangChain + Groq and converts them to PDF
# """

# import logging
# import json
# import asyncio
# from typing import Dict, Optional, List
# from datetime import datetime
# from pathlib import Path

# import markdown
# from weasyprint import HTML

# from langchain_groq import ChatGroq
# from langchain_core.prompts import PromptTemplate
# from langchain_core.output_parsers import StrOutputParser

# from config import config
# from human_loop import PersonalProfile, get_missing_profile_info

# logger = logging.getLogger(__name__)


# class CVEngine:
#     """Generate tailored CVs based on job requirements and personal profile"""

#     def __init__(self):

#         # Groq LLM
#         self.llm = ChatGroq(
#             groq_api_key=config.GROQ_API_KEY,
#             model_name="llama-3.1-8b-instant",
#             temperature=0.3
#         )

#         self.output_parser = StrOutputParser()
#         self.cv_template = self._load_cv_template()

#     # ---------------------------------------------------
#     # Template Handling
#     # ---------------------------------------------------

#     def _load_cv_template(self) -> str:

#         template_path = config.TEMPLATES_DIR / "cv_template.html"

#         if template_path.exists():
#             with open(template_path, "r") as f:
#                 return f.read()

#         default_template = self._create_default_template()

#         with open(template_path, "w") as f:
#             f.write(default_template)

#         return default_template
    
#     def _select_relevant_projects(self, job_data: Dict, profile: PersonalProfile):

#         job_skills = " ".join(job_data.get("skills_required", [])).lower()


#         projects = []

#         all_projects = [
#             {
#             "name": profile.project_1_name,
#             "desc": profile.project_1_description,
#             "tech": profile.project_1_tech_stack
#             },
#             {
#             "name": profile.project_2_name,
#             "desc": profile.project_2_description,
#             "tech": profile.project_2_tech_stack
#             },
#             {
#             "name": profile.project_3_name,
#             "desc": profile.project_3_description,
#             "tech": profile.project_3_tech_stack
#             }
#         ]

#         scored_projects = []

#         for p in all_projects:

#             if not p["name"]:
#                 continue

#         tech = (p["tech"] or "").lower()

#         score = sum(skill.lower() in tech for skill in job_skills.split())

#         scored_projects.append((score, p))

#         scored_projects.sort(reverse=True, key=lambda x: x[0])

#         selected = [p for _, p in scored_projects[:2]]

#         formatted = []

#         for p in selected:
#             formatted.append(
#                 f"{p['name']} | Tech: {p['tech']} | {p['desc']}"
#             )

#         return "\n".join(formatted)

#     def _create_default_template(self) -> str:

#         return """
# <!DOCTYPE html>
# <html>
# <head>
# <meta charset="UTF-8">
# <title>{full_name} - Resume</title>

# <style>

# body {
# font-family: Arial, sans-serif;
# line-height: 1.6;
# margin: 20px;
# color: #333;
# }

# .header {
# text-align: center;
# border-bottom: 2px solid #007acc;
# padding-bottom: 15px;
# margin-bottom: 25px;
# }

# .name {
# font-size: 28px;
# font-weight: bold;
# color: #007acc;
# }

# .contact-info {
# font-size: 14px;
# color: #666;
# }

# .section {
# margin-bottom: 25px;
# }

# .section-title {
# font-size: 18px;
# font-weight: bold;
# color: #007acc;
# border-bottom: 1px solid #ddd;
# margin-bottom: 10px;
# }

# .subsection {
# margin-bottom: 12px;
# }

# .skills {
# display: flex;
# flex-wrap: wrap;
# gap: 8px;
# }

# .skill-tag {
# border: 1px solid #007acc;
# padding: 3px 8px;
# border-radius: 4px;
# font-size: 12px;
# }

# ul {
# margin: 5px 0;
# padding-left: 20px;
# }

# </style>
# </head>

# <body>

# {content}

# </body>
# </html>
# """

#     # ---------------------------------------------------
#     # CV Generation
#     # ---------------------------------------------------

#     async def generate_tailored_cv(self, job_data: Dict, profile: PersonalProfile) -> Optional[str]:

#         prompt = self._create_cv_prompt(job_data, profile)

#         try:

#             prompt_template = PromptTemplate(
#                 input_variables=["prompt"],
#                 template="{prompt}"
#             )

#             chain = prompt_template | self.llm | self.output_parser

#             response = await chain.ainvoke({"prompt": prompt})

#             return response.strip()

#         except Exception as e:
#             logger.error(f"CV generation error: {e}")
#             return None

#     # ---------------------------------------------------
#     # Prompt Builder
#     # ---------------------------------------------------

#     def _create_cv_prompt(self, job_data: Dict, profile: PersonalProfile) -> str:

#         job_title = job_data.get("title", "")
#         company = job_data.get("company", "")

#         # Extract job skills
#         job_skills = " ".join(job_data.get("skills_required", [])).lower()

#         # Collect candidate skills
#         candidate_skills = (
#         f"{profile.programming_languages}, "
#         f"{profile.frameworks}, "
#         f"{profile.databases}, "
#         f"{profile.tools}"
#         )

#     # Match skills between candidate and job
#         matched_skills = [
#         s.strip()
#         for s in candidate_skills.split(",")
#         if s.strip().lower() in job_skills
#         ]   

#         return f"""
# You are an expert resume writer.

# Create a professional ATS-friendly resume in HTML BODY format.

# JOB DETAILS

# Title: {job_title}
# Company: {company}

# Required Skills:
# {job_data.get("skills_required", [])}


# CANDIDATE PROFILE

# Name: {profile.full_name}
# Email: {profile.email}
# Phone: {profile.phone}
# Location: {profile.location}

# LinkedIn: {profile.linkedin_url}
# Github: {profile.github_url}

# Experience:
# Role: {profile.current_role}
# Company: {profile.current_company}
# Years: {profile.years_experience}


# CANDIDATE SKILLS

# Languages: {profile.programming_languages}
# Frameworks: {profile.frameworks}
# Databases: {profile.databases}
# Tools: {profile.tools}


# SKILLS MATCHING THE JOB
# {", ".join(matched_skills)}


# Education:
# {profile.degree} in {profile.field_of_study}
# {profile.university}
# CGPA: {profile.cgpa}


# Projects (Use the most relevant ones for the job):
# {self._select_relevant_projects(job_data, profile)}


# Achievements:
# {profile.achievement_1}
# {profile.achievement_2}
# {profile.achievement_3}


# IMPORTANT RULES

# 1. Do NOT create fake experience.
# 2. Experience must ONLY use the candidate experience provided above.
# 3. Do NOT use the job company as work experience.
# 4. Use the matched skills to tailor the resume.
# 5. Highlight projects most relevant to the job.


# HTML STRUCTURE

# Use the following structure:

# <div class="section">
# <div class="section-title">Summary</div>
# Professional summary tailored for the job.
# </div>

# <div class="section">
# <div class="section-title">Skills</div>
# List the most relevant skills matching the job.
# </div>

# <div class="section">
# <div class="section-title">Experience</div>
# Use ONLY the candidate experience provided.
# </div>

# <div class="section">
# <div class="section-title">Projects</div>
# Use ONLY the selected projects provided above.
# </div>

# <div class="section">
# <div class="section-title">Education</div>
# Candidate education details.
# </div>

# Return only HTML BODY content.
# """

#     # ---------------------------------------------------
#     # Project Formatter
#     # ---------------------------------------------------

#     # def _format_projects(self, profile: PersonalProfile):

#     #     projects = []

#     #     if profile.project_1_name:
#     #         projects.append(
#     #             f"{profile.project_1_name} - {profile.project_1_description}"
#     #         )

#     #     if profile.project_2_name:
#     #         projects.append(
#     #             f"{profile.project_2_name} - {profile.project_2_description}"
#     #         )

#     #     if profile.project_3_name:
#     #         projects.append(
#     #             f"{profile.project_3_name} - {profile.project_3_description}"
#     #         )

#     #     return "\n".join(projects)


#     # ---------------------------------------------------
#     # PDF Generator
#     # ---------------------------------------------------

#     def create_cv_pdf(self, cv_content: str, filename: str, profile: PersonalProfile):

#         try:

#             # html_content = self.cv_template.format(
#             #     full_name=profile.full_name,
#             #     content=cv_content
#             # )
#             html_content = self.cv_template.replace("{full_name}", profile.full_name)
#             html_content = html_content.replace("{content}", cv_content)

#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

#             output_file = config.OUTPUT_DIR / f"{filename}_{timestamp}.pdf"

#             HTML(string=html_content).write_pdf(output_file)

#             logger.info(f"CV created: {output_file}")

#             return str(output_file)

#         except Exception as e:

#             logger.error(f"PDF generation error: {e}")
#             return None

#     # ---------------------------------------------------
#     # Full CV Pipeline
#     # ---------------------------------------------------

#     async def generate_cv_for_job(self, job_data: Dict):

#         profile = PersonalProfile.load_from_file()

#         missing = get_missing_profile_info(profile)

#         if missing:
#             logger.warning(f"Missing profile fields: {missing}")
#             return None

#         cv_content = await self.generate_tailored_cv(job_data, profile)

#         if not cv_content:
#             return None

#         job_title = job_data.get("title", "job").replace(" ", "_")

#         company = job_data.get("company", "company").replace(" ", "_")

#         filename = f"cv_{job_title}_{company}".lower()

#         pdf_path = self.create_cv_pdf(cv_content, filename, profile)

#         if pdf_path:
#             await self._save_cv_metadata(job_data, pdf_path, profile)

#         return pdf_path

#     # ---------------------------------------------------
#     # Metadata Storage
#     # ---------------------------------------------------

#     async def _save_cv_metadata(self, job_data, pdf_path, profile):

#         metadata = {

#             "generated_at": datetime.now().isoformat(),
#             "job_title": job_data.get("title"),
#             "company": job_data.get("company"),
#             "pdf_path": pdf_path,
#             "candidate": profile.full_name
#         }

#         metadata_file = config.DATA_DIR / "cv_metadata.json"

#         existing = []

#         if metadata_file.exists():

#             with open(metadata_file, "r") as f:
#                 existing = json.load(f)

#         existing.append(metadata)

#         with open(metadata_file, "w") as f:
#             json.dump(existing, f, indent=2)

#     # ---------------------------------------------------
#     # Batch CV Generator
#     # ---------------------------------------------------

#     async def batch_generate_cvs(self, jobs: List[Dict]):

#         tasks = [
#             self.generate_cv_for_job(job)
#             for job in jobs
#         ]

#         results = await asyncio.gather(*tasks)

#         return [r for r in results if r]


# # ---------------------------------------------------
# # Simple Markdown CV Engine
# # ---------------------------------------------------

# class SimpleCVEngine:

#     def __init__(self):

#         self.llm = ChatGroq(
#             groq_api_key=config.GROQ_API_KEY,
#             model_name="llama3-70b-8192",
#             temperature=0.3
#         )

#     async def generate_markdown_cv(self, job_data, profile):

#         prompt = f"""
# Create a professional resume in markdown.

# Job: {job_data.get('title')}
# Company: {job_data.get('company')}

# Candidate: {profile.full_name}
# Skills: {profile.programming_languages}
# Experience: {profile.years_experience}

# Return markdown only.
# """

#         response = await self.llm.ainvoke(prompt)

#         return response.content

#     def markdown_to_html(self, markdown_content, profile):

#         html = markdown.markdown(markdown_content)

#         return f"""
# <html>
# <head>
# <title>{profile.full_name}</title>
# </head>

# <body>

# {html}

# </body>
# </html>
# """


# # ---------------------------------------------------
# # Test Script
# # ---------------------------------------------------

# async def test_cv_engine():

#     job_data = {

#         "title": "Python Developer",
#         "company": "TechCorp",

#         "skills_required": [
#             "Python",
#             "FastAPI",
#             "PostgreSQL"
#         ]
#     }

#     engine = CVEngine()

#     result = await engine.generate_cv_for_job(job_data)

#     print("Generated CV:", result)


# if __name__ == "__main__":

#     asyncio.run(test_cv_engine())
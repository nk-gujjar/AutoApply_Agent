"""
File loader for cached jobs from naukri_jobs.txt
Parses the formatted job text file and returns structured job data
"""

import re
from pathlib import Path
from typing import List, Dict, Any
from modules.core.config.settings import config, logger


def parse_naukri_jobs_file(file_path: Path = None) -> List[Dict[str, Any]]:
    """
    Parse naukri_jobs.txt file and extract job details.
    
    Args:
        file_path: Path to the naukri_jobs.txt file. Defaults to data/naukri_jobs.txt
    
    Returns:
        List of job dictionaries with standardized fields
    """
    if file_path is None:
        file_path = config.JOBS_DIR / "naukri_jobs.txt"
    
    if not file_path.exists():
        logger.warning(f"Jobs file not found: {file_path}")
        return []
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception(f"Failed to read jobs file: {file_path}")
        return []
    
    jobs = []
    # Split by the separator line
    job_blocks = content.split("=================================================================\n")
    
    for block in job_blocks:
        block = block.strip()
        if not block:
            continue
        
        job_dict = parse_job_block(block)
        if job_dict:
            jobs.append(job_dict)
    
    logger.info(f"Loaded {len(jobs)} jobs from file: {file_path}")
    return jobs


def parse_job_block(block: str) -> Dict[str, Any]:
    """
    Parse a single job block from the naukri_jobs.txt file.
    
    Expected format:
    Title              : Job Title
    Company            : Company Name
    Location           : City
    Experience         : 0-2 Yrs
    CTC / Salary       : Amount or Not mentioned
    Apply Type         : easy_apply/external
    Apply Status       : apply/already_applied
    External Apply Link: URL (optional)
    JD Source          : LLM Summary
    Filter Status      : passed
    Role Category      : role-type
    Listing Page       : page number
    Scraped At         : ISO timestamp
    Naukri Link        : URL
    """
    job = {}
    
    # Extract fields using regex patterns
    patterns = {
        "title": r"Title\s*:\s*(.+?)(?=\n|$)",
        "company": r"Company\s*:\s*(.+?)(?=\n|$)",
        "location": r"Location\s*:\s*(.+?)(?=\n|$)",
        "experience": r"Experience\s*:\s*(.+?)(?=\n|$)",
        "ctc": r"CTC / Salary\s*:\s*(.+?)(?=\n|$)",
        "apply_type": r"Apply Type\s*:\s*(.+?)(?=\n|$)",
        "apply_status": r"Apply Status\s*:\s*(.+?)(?=\n|$)",
        "link": r"(?:Naukri Link|External Apply Link)\s*:\s*(https?://\S+?)(?=\n|$)",
        "jd_source": r"JD Source\s*:\s*(.+?)(?=\n|$)",
        "filter_status": r"Filter Status\s*:\s*(.+?)(?=\n|$)",
        "role_category": r"Role Category\s*:\s*(.+?)(?=\n|$)",
        "page_no": r"Listing Page\s*:\s*(\d+)",
        "scraped_at": r"Scraped At\s*:\s*(.+?)(?=\n|$)",
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, block)
        if match:
            job[field] = match.group(1).strip()
    
    # Extract JD summary from the "--- Job Details (LLM-extracted) ---" section
    jd_match = re.search(
        r"--- Job Details \(LLM-extracted\) ---\s*\n(.*?)(?==|$)",
        block,
        re.DOTALL
    )
    if jd_match:
        job["jd_summary"] = jd_match.group(1).strip()
        job["jd_llm_used"] = True
    else:
        job["jd_summary"] = ""
        job["jd_llm_used"] = False
    
    # Convert page_no to int if present
    if "page_no" in job:
        try:
            job["page_no"] = int(job["page_no"])
        except (ValueError, TypeError):
            job["page_no"] = 1
    
    # Ensure all required fields exist
    required_fields = [
        "title",
        "company",
        "location",
        "experience",
        "ctc",
        "apply_type",
        "apply_status",
        "link",
        "role_category",
    ]
    
    for field in required_fields:
        if field not in job:
            job[field] = "Not mentioned"
    
    return job if job.get("title") else None


def load_cached_jobs(max_jobs: int = 10) -> List[Dict[str, Any]]:
    """
    Load jobs from cache file with optional limit.
    
    Args:
        max_jobs: Maximum number of jobs to return
    
    Returns:
        List of job dictionaries (up to max_jobs)
    """
    jobs = parse_naukri_jobs_file()
    return jobs[:max_jobs] if jobs else []

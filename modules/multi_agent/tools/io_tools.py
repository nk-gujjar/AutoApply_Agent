import json
from pathlib import Path
from typing import Any, Dict, List


class WorkspaceIOTools:
    @staticmethod
    async def load_naukri_jobs_file(file_path: str = "./data/naukri_jobs.txt") -> List[Dict[str, str]]:
        path = Path(file_path)
        if not path.exists():
            return []

        jobs: List[Dict[str, str]] = []
        current_job: Dict[str, str] = {}

        with path.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()

                if line.startswith("Title"):
                    current_job["title"] = line.split(":", 1)[1].strip()
                elif line.startswith("Company"):
                    current_job["company"] = line.split(":", 1)[1].strip()
                elif line.startswith("Location"):
                    current_job["location"] = line.split(":", 1)[1].strip()
                elif line.startswith("Experience"):
                    current_job["experience"] = line.split(":", 1)[1].strip()
                elif line.startswith("Naukri Link") or line.startswith("Apply Link"):
                    current_job["link"] = line.split(":", 1)[1].strip()
                elif line.startswith("=") and current_job.get("link"):
                    jobs.append(current_job)
                    current_job = {}

        return jobs

    @staticmethod
    async def save_json(data: Any, file_path: str) -> str:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        return str(path)

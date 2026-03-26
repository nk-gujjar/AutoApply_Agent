# """
# Processor Module
# Uses Google Generative AI (Gemini) to parse unstructured job descriptions
# into structured JSON format
# """

# import google.generativeai as genai
# from langchain_google_genai import ChatGoogleGenerativeAI
# import json
# import logging
# from typing import Dict, Optional, List
# from pydantic import BaseModel, Field, ValidationError
# from datetime import datetime
# import re
# import asyncio
# import os

# from config import config

# logger = logging.getLogger(__name__)

# # Configure Gemini API
# genai.configure(api_key=config.GEMINI_API_KEY)

# class JobRequirement(BaseModel):
#     """Pydantic model for structured job requirements"""
#     title: str = Field(..., description="Job title/role")
#     company: Optional[str] = Field(None, description="Company name")
#     location: Optional[str] = Field(None, description="Job location")
#     experience_min: Optional[int] = Field(None, description="Minimum years of experience required")
#     experience_max: Optional[int] = Field(None, description="Maximum years of experience required")
#     ctc_min: Optional[float] = Field(None, description="Minimum CTC in LPA")
#     ctc_max: Optional[float] = Field(None, description="Maximum CTC in LPA")
#     skills_required: List[str] = Field(default=[], description="List of required skills")
#     skills_preferred: List[str] = Field(default=[], description="List of preferred skills")
#     job_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, Internship")
#     work_mode: Optional[str] = Field(None, description="Remote, On-site, Hybrid")
#     description: str = Field(..., description="Job description")
#     responsibilities: List[str] = Field(default=[], description="Key responsibilities")
#     qualifications: List[str] = Field(default=[], description="Required qualifications")
#     application_url: Optional[str] = Field(None, description="Application URL")
#     application_email: Optional[str] = Field(None, description="Application email")
#     application_deadline: Optional[str] = Field(None, description="Application deadline")
#     benefits: List[str] = Field(default=[], description="Benefits offered")
#     industry: Optional[str] = Field(None, description="Industry/domain")
#     company_size: Optional[str] = Field(None, description="Company size")

# class JobProcessor:
#     """Process and structure job information using Gemini AI"""
    
#     def __init__(self):
#         self.model = genai.GenerativeModel('gemini-1.5-flash')
#         self.processing_prompt = self._create_processing_prompt()
    
#     def _create_processing_prompt(self) -> str:
#         """Create the prompt template for job processing"""
#         return """
#         You are an expert job posting analyzer. Parse the following unstructured job posting text and extract relevant information into a structured JSON format.

#         Extract the following information if available:
#         - Job title/role
#         - Company name
#         - Location (city, state, country)
#         - Experience requirements (min and max years)
#         - CTC/Salary range (in LPA - Lakhs Per Annum)
#         - Required skills (programming languages, frameworks, tools)
#         - Preferred skills
#         - Job type (Full-time, Part-time, Contract, Internship)
#         - Work mode (Remote, On-site, Hybrid)
#         - Job description
#         - Key responsibilities
#         - Required qualifications (education, certifications)
#         - Application URL or email
#         - Application deadline
#         - Benefits offered
#         - Industry/domain
#         - Company size

#         Job Posting Text:
#         {job_text}

#         Please return the information as a valid JSON object with the following structure:
#         {{
#             "title": "Job Title",
#             "company": "Company Name or null",
#             "location": "Location or null",
#             "experience_min": number or null,
#             "experience_max": number or null,
#             "ctc_min": number or null,
#             "ctc_max": number or null,
#             "skills_required": ["skill1", "skill2"],
#             "skills_preferred": ["skill1", "skill2"],
#             "job_type": "Full-time/Part-time/Contract/Internship or null",
#             "work_mode": "Remote/On-site/Hybrid or null",
#             "description": "Full job description",
#             "responsibilities": ["responsibility1", "responsibility2"],
#             "qualifications": ["qualification1", "qualification2"],
#             "application_url": "URL or null",
#             "application_email": "email@company.com or null",
#             "application_deadline": "deadline or null",
#             "benefits": ["benefit1", "benefit2"],
#             "industry": "Industry or null",
#             "company_size": "Startup/Small/Medium/Large/Enterprise or null"
#         }}

#         Important:
#         - If information is not available, use null for single values and empty arrays for lists
#         - For experience, extract numbers only (e.g., "2-5 years" becomes experience_min: 2, experience_max: 5)
#         - For CTC, convert to LPA format (e.g., "15-20 lakhs" becomes ctc_min: 15, ctc_max: 20)
#         - Keep skills as simple strings without complex descriptions
#         - Return only valid JSON, no additional text or formatting
#         """
    
#     async def process_job_posting(self, job_text: str, urls: List[str] = None) -> Optional[JobRequirement]:
#         """Process a job posting and return structured information"""
#         try:
#             # Combine job text with URLs if available
#             full_text = job_text
#             if urls:
#                 full_text += f"\n\nURLs found: {', '.join(urls)}"
            
#             # Generate response using Gemini
#             prompt = self.processing_prompt.format(job_text=full_text)
#             response = await self._generate_response(prompt)
            
#             if not response:
#                 logger.error("No response from Gemini API")
#                 return None
            
#             # Parse JSON response
#             try:
#                 job_data = json.loads(response)
#             except json.JSONDecodeError as e:
#                 logger.error(f"Failed to parse JSON response: {e}")
#                 logger.error(f"Raw response: {response}")
#                 return None
            
#             # Validate and create JobRequirement object
#             try:
#                 job_requirement = JobRequirement(**job_data)
#                 logger.info(f"Successfully processed job: {job_requirement.title}")
#                 return job_requirement
#             except ValidationError as e:
#                 logger.error(f"Validation error: {e}")
#                 logger.error(f"Job data: {job_data}")
#                 return None
                
#         except Exception as e:
#             logger.error(f"Error processing job posting: {e}")
#             return None
    
#     async def _generate_response(self, prompt: str, max_retries: int = 3) -> Optional[str]:
#         """Generate response from Gemini with retry logic"""
#         for attempt in range(max_retries):
#             try:
#                 response = self.model.generate_content(prompt)
#                 if response and response.text:
#                     return response.text.strip()
#                 else:
#                     logger.warning(f"Empty response from Gemini (attempt {attempt + 1})")
#             except Exception as e:
#                 logger.error(f"Error generating response (attempt {attempt + 1}): {e}")
#                 if attempt < max_retries - 1:
#                     await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
#         return None
    
#     def extract_urls_from_text(self, text: str) -> List[str]:
#         """Extract URLs from job posting text"""
#         url_pattern = re.compile(
#             r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
#         )
#         urls = url_pattern.findall(text)
#         return urls
    
#     async def enhance_with_url_content(self, job_requirement: JobRequirement, urls: List[str]) -> JobRequirement:
#         """Enhance job requirement with content from URLs"""
#         if not urls:
#             return job_requirement
        
#         # For now, we'll just add the first URL as application_url if not already present
#         if not job_requirement.application_url and urls:
#             job_requirement.application_url = urls[0]
        
#         # In a full implementation, you might want to scrape the URL content
#         # and extract additional information using Gemini
        
#         return job_requirement
    
#     async def process_batch_jobs(self, jobs_data: List[Dict]) -> List[JobRequirement]:
#         """Process multiple job postings"""
#         processed_jobs = []
        
#         for job_data in jobs_data:
#             try:
#                 # Extract job text and URLs
#                 job_text = job_data.get('raw_text', '')
#                 urls = job_data.get('urls', [])
                
#                 # Process the job
#                 job_requirement = await self.process_job_posting(job_text, urls)
                
#                 if job_requirement:
#                     # Add metadata from original scraping
#                     job_requirement_dict = job_requirement.dict()
#                     job_requirement_dict.update({
#                         'source_channel': job_data.get('channel'),
#                         'message_id': job_data.get('message_id'),
#                         'message_date': job_data.get('message_date'),
#                         'message_link': job_data.get('message_link'),
#                         'processed_at': datetime.now().isoformat()
#                     })
                    
#                     # Create enhanced JobRequirement
#                     processed_jobs.append(job_requirement_dict)
                    
#             except Exception as e:
#                 logger.error(f"Error processing job from batch: {e}")
#                 continue
        
#         logger.info(f"Processed {len(processed_jobs)} jobs from batch of {len(jobs_data)}")
#         return processed_jobs
    
#     async def save_processed_jobs(self, jobs: List[Dict], filename: str = None):
#         """Save processed jobs to file"""
#         if not filename:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             filename = f"processed_jobs_{timestamp}.json"
        
#         filepath = config.DATA_DIR / filename
        
#         with open(filepath, 'w') as f:
#             json.dump(jobs, f, indent=2)
        
#         logger.info(f"Saved {len(jobs)} processed jobs to {filepath}")
#         return filepath
    
#     def filter_jobs_by_criteria(self, jobs: List[Dict]) -> List[Dict]:
#         """Filter jobs based on user criteria"""
#         filtered_jobs = []
        
#         for job in jobs:
#             # Check experience criteria
#             if job.get('experience_min') is not None:
#                 if job['experience_min'] > config.MAX_EXPERIENCE:
#                     continue
            
#             if job.get('experience_max') is not None:
#                 if job['experience_max'] < config.MIN_EXPERIENCE:
#                     continue
            
#             # Check CTC criteria
#             if job.get('ctc_min') is not None:
#                 if job['ctc_min'] < config.MIN_CTC:
#                     continue
            
#             # Check if job title matches target roles
#             job_title = job.get('title', '').lower()
#             role_matches = any(role.lower() in job_title for role in config.TARGET_ROLES)
            
#             if role_matches:
#                 filtered_jobs.append(job)
        
#         logger.info(f"Filtered {len(filtered_jobs)} jobs from {len(jobs)} total jobs")
#         return filtered_jobs

# # Example usage and testing
# async def test_processor():
#     """Test the processor functionality"""
#     processor = JobProcessor()
    
#     sample_job_text = """
#     🚀 Hiring: Senior Python Developer at TechCorp
    
#     Location: Bangalore, India
#     Experience: 3-5 years
#     CTC: 18-25 LPA
    
#     We are looking for a skilled Python developer to join our backend team.
    
#     Requirements:
#     - Strong experience with Python, Django, FastAPI
#     - Knowledge of PostgreSQL, Redis
#     - Experience with AWS, Docker
#     - Bachelor's degree in Computer Science
    
#     Responsibilities:
#     - Develop and maintain APIs
#     - Optimize database queries
#     - Collaborate with frontend team
    
#     Benefits:
#     - Health insurance
#     - Flexible working hours
#     - Remote work option
    
#     Apply at: https://techcorp.com/careers/python-dev
#     Email: careers@techcorp.com
#     """
    
#     result = await processor.process_job_posting(sample_job_text)
#     if result:
#         print("Processed job:")
#         print(json.dumps(result.dict(), indent=2))
#     else:
#         print("Failed to process job")

# if __name__ == "__main__":
#     asyncio.run(test_processor())


"""
Processor Module
Uses LangChain + Groq to parse unstructured job descriptions
"""

import json
import logging
import asyncio
from typing import Optional, List

from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage

from config import create_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobRequirement(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None

    experience_min: Optional[int] = None
    experience_max: Optional[int] = None

    ctc_min: Optional[float] = None
    ctc_max: Optional[float] = None

    skills_required: List[str] = []
    skills_preferred: List[str] = []

    job_type: Optional[str] = None
    work_mode: Optional[str] = None

    description: Optional[str] = None

    responsibilities: List[str] = []
    qualifications: List[str] = []

    application_url: Optional[str] = None
    application_email: Optional[str] = None
    application_deadline: Optional[str] = None

    benefits: List[str] = []

    industry: Optional[str] = None
    company_size: Optional[str] = None


class JobProcessor:

    def __init__(self):

        self.llm = create_llm(temperature=0)

        self.processing_prompt = self._create_processing_prompt()

    def _create_processing_prompt(self):

        return """
You are an expert job posting analyzer.

Extract job information and return ONLY valid JSON.

If information is missing:
- use null
- use [] for lists

Return JSON in this format:

{{
"title": "",
"company": null,
"location": null,
"experience_min": null,
"experience_max": null,
"ctc_min": null,
"ctc_max": null,
"skills_required": [],
"skills_preferred": [],
"job_type": null,
"work_mode": null,
"description": "",
"responsibilities": [],
"qualifications": [],
"application_url": null,
"application_email": null,
"application_deadline": null,
"benefits": [],
"industry": null,
"company_size": null
}}

Job Posting:
{job_text}
"""

    async def process_job_posting(self, job_text: str, urls: List[str] = None):

        try:

            full_text = job_text

            if urls:
                full_text += f"\nURLs: {', '.join(urls)}"

            prompt = self.processing_prompt.format(job_text=full_text)

            print("\n================ PROMPT SENT TO LLM ================\n")
            print(prompt)

            response = await self._generate_response(prompt)

            if not response:
                print("\n❌ No response from LLM\n")
                return None

            print("\n================ RAW LLM RESPONSE ================\n")
            print(response)

            response = response.strip()

            if response.startswith("```"):
                response = response.replace("```json", "").replace("```", "").strip()

            job_data = json.loads(response)

            print("\n================ PARSED JSON ================\n")
            print(json.dumps(job_data, indent=2))

            job_requirement = JobRequirement(**job_data)

            print("\n================ FINAL STRUCTURED OUTPUT ================\n")
            print(json.dumps(job_requirement.dict(), indent=2))

            logger.info(f"Processed job: {job_requirement.title}")

            return job_requirement

        except Exception as e:
            logger.error(f"Error processing job: {e}")
            return None

    async def _generate_response(self, prompt: str, retries: int = 3):

        for attempt in range(retries):

            try:

                messages = [
                    SystemMessage(content="Extract structured data from job posts."),
                    HumanMessage(content=prompt)
                ]

                response = await self.llm.ainvoke(messages)

                if response and response.content:
                    return response.content

            except Exception as e:

                logger.error(f"Attempt {attempt+1} failed: {e}")

                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return None


async def test_processor():

    processor = JobProcessor()

    sample_job = """
Hiring: Senior Python Developer

Location: Bangalore
Experience: 3-5 years
CTC: 18-25 LPA

Requirements:
Python, Django, FastAPI
PostgreSQL, Redis
AWS, Docker

Responsibilities:
Develop APIs
Optimize database queries

Apply at: https://techcorp.com/careers
"""

    result = await processor.process_job_posting(sample_job)

    if result:
        print("\n✅ SUCCESS\n")
    else:
        print("\n❌ FAILED\n")


if __name__ == "__main__":
    asyncio.run(test_processor())
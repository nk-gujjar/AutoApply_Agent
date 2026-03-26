"""
Human Loop Module
Handles missing profile information by prompting the user
Uses Pydantic models for validation and updates personal.txt file
"""

import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError
import configparser
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)

class PersonalProfile(BaseModel):
    """Pydantic model for personal profile validation"""
    
    # Personal Information
    full_name: Optional[str] = Field(None, description="Full name")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    location: Optional[str] = Field(None, description="Current location")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    portfolio_url: Optional[str] = Field(None, description="Portfolio website URL")
    
    # Professional Summary
    current_role: Optional[str] = Field(None, description="Current job title")
    years_experience: Optional[int] = Field(None, description="Years of experience")
    total_experience_months: Optional[int] = Field(None, description="Total experience in months")
    current_company: Optional[str] = Field(None, description="Current company name")
    notice_period: Optional[str] = Field(None, description="Notice period")
    expected_ctc: Optional[float] = Field(None, description="Expected CTC in LPA")
    current_ctc: Optional[float] = Field(None, description="Current CTC in LPA")
    
    # Skills
    programming_languages: Optional[str] = Field(None, description="Programming languages")
    frameworks: Optional[str] = Field(None, description="Frameworks and libraries")
    databases: Optional[str] = Field(None, description="Database technologies")
    cloud_platforms: Optional[str] = Field(None, description="Cloud platforms")
    tools: Optional[str] = Field(None, description="Tools and technologies")
    other_skills: Optional[str] = Field(None, description="Other relevant skills")
    
    # Education
    degree: Optional[str] = Field(None, description="Highest degree")
    field_of_study: Optional[str] = Field(None, description="Field of study")
    university: Optional[str] = Field(None, description="University/Institute name")
    graduation_year: Optional[int] = Field(None, description="Graduation year")
    cgpa: Optional[float] = Field(None, description="CGPA/Grade")
    
    # Certifications
    cert_1: Optional[str] = Field(None, description="Certification 1")
    cert_2: Optional[str] = Field(None, description="Certification 2")
    cert_3: Optional[str] = Field(None, description="Certification 3")
    
    # Projects
    project_1_name: Optional[str] = Field(None, description="Project 1 name")
    project_1_description: Optional[str] = Field(None, description="Project 1 description")
    project_1_tech_stack: Optional[str] = Field(None, description="Project 1 tech stack")
    project_1_github: Optional[str] = Field(None, description="Project 1 GitHub URL")
    project_1_duration: Optional[str] = Field(None, description="Project 1 duration of work")
    
    project_2_name: Optional[str] = Field(None, description="Project 2 name")
    project_2_description: Optional[str] = Field(None, description="Project 2 description")
    project_2_tech_stack: Optional[str] = Field(None, description="Project 2 tech stack")
    project_2_github: Optional[str] = Field(None, description="Project 2 GitHub URL")
    project_2_duration: Optional[str] = Field(None, description="Project 2 duration of work")
    
    project_3_name: Optional[str] = Field(None, description="Project 3 name")
    project_3_description: Optional[str] = Field(None, description="Project 3 description")
    project_3_tech_stack: Optional[str] = Field(None, description="Project 3 tech stack")
    project_3_github: Optional[str] = Field(None, description="Project 3 GitHub URL")
    project_3_duration: Optional[str] = Field(None, description="Project 3 duration of work")

    project_4_name: Optional[str] = Field(None, description="Project 4 name")
    project_4_description: Optional[str] = Field(None, description="Project 4 description")
    project_4_tech_stack: Optional[str] = Field(None, description="Project 4 tech stack")
    project_4_github: Optional[str] = Field(None, description="Project 4 GitHub URL")
    project_4_duration: Optional[str] = Field(None, description="Project 4 duration of work")

    project_5_name: Optional[str] = Field(None, description="Project 5 name")
    project_5_description: Optional[str] = Field(None, description="Project 5 description")
    project_5_tech_stack: Optional[str] = Field(None, description="Project 5 tech stack")
    project_5_github: Optional[str] = Field(None, description="Project 5 GitHub URL")
    project_5_duration: Optional[str] = Field(None, description="Project 5 duration of work")

    project_6_name: Optional[str] = Field(None, description="Project 6 name")
    project_6_description: Optional[str] = Field(None, description="Project 6 description")
    project_6_tech_stack: Optional[str] = Field(None, description="Project 6 tech stack")
    project_6_github: Optional[str] = Field(None, description="Project 6 GitHub URL")
    project_6_duration: Optional[str] = Field(None, description="Project 6 duration of work")

    # Achievements
    achievement_1: Optional[str] = Field(None, description="Achievement 1")
    achievement_2: Optional[str] = Field(None, description="Achievement 2")
    achievement_3: Optional[str] = Field(None, description="Achievement 3")
    
    # Preferences
    preferred_work_mode: Optional[str] = Field(None, description="Preferred work mode")
    preferred_locations: Optional[str] = Field(None, description="Preferred work locations")
    preferred_company_size: Optional[str] = Field(None, description="Preferred company size")
    preferred_industries: Optional[str] = Field(None, description="Preferred industries")
    
    @classmethod
    def load_from_file(cls) -> 'PersonalProfile':
        """Load personal profile from personal.txt file"""
        profile_path = config.PERSONAL_PROFILE_PATH
        
        if not profile_path.exists():
            logger.error(f"Personal profile file not found: {profile_path}")
            return cls()
        
        try:
            # Read the configuration file
            config_parser = configparser.ConfigParser()
            config_parser.read(profile_path)
            
            # Extract data from all sections
            profile_data = {}
            for section_name in config_parser.sections():
                for key, value in config_parser.items(section_name):
                    # Convert empty strings to None
                    if value.strip() == '':
                        profile_data[key] = None
                    else:
                        # Try to convert numeric values
                        try:
                            if '.' in value:
                                profile_data[key] = float(value)
                            else:
                                profile_data[key] = int(value)
                        except ValueError:
                            profile_data[key] = value.strip()
            
            return cls(**profile_data)
            
        except Exception as e:
            logger.error(f"Error loading profile from file: {e}")
            return cls()
    
    def save_to_file(self):
        """Save personal profile to personal.txt file"""
        profile_path = config.PERSONAL_PROFILE_PATH
        
        try:
            # Create ConfigParser object
            config_parser = configparser.ConfigParser()
            
            # Define section mappings
            sections = {
                'PERSONAL_INFO': [
                    'full_name', 'email', 'phone', 'location', 
                    'linkedin_url', 'github_url', 'portfolio_url'
                ],
                'PROFESSIONAL_SUMMARY': [
                    'current_role', 'years_experience', 'total_experience_months',
                    'current_company', 'notice_period', 'expected_ctc', 'current_ctc'
                ],
                'SKILLS': [
                    'programming_languages', 'frameworks', 'databases',
                    'cloud_platforms', 'tools', 'other_skills'
                ],
                'EDUCATION': [
                    'degree', 'field_of_study', 'university', 'graduation_year', 'cgpa'
                ],
                'CERTIFICATIONS': [
                    'cert_1', 'cert_2', 'cert_3'
                ],
                'PROJECTS': [
                    'project_1_name', 'project_1_description', 'project_1_tech_stack', 'project_1_github','project_1_duration',
                    'project_2_name', 'project_2_description', 'project_2_tech_stack', 'project_2_github','project_2_duration',
                    'project_3_name', 'project_3_description', 'project_3_tech_stack', 'project_3_github','project_3_duration'
                ],
                'ACHIEVEMENTS': [
                    'achievement_1', 'achievement_2', 'achievement_3'
                ],
                'PREFERENCES': [
                    'preferred_work_mode', 'preferred_locations', 'preferred_company_size', 'preferred_industries'
                ]
            }
            
            # Add sections and values
            for section_name, fields in sections.items():
                config_parser.add_section(section_name)
                for field in fields:
                    value = getattr(self, field)
                    config_parser.set(section_name, field, str(value) if value is not None else '')
            
            # Write to file
            with open(profile_path, 'w') as f:
                config_parser.write(f)
            
            logger.info(f"Profile saved to {profile_path}")
            
        except Exception as e:
            logger.error(f"Error saving profile to file: {e}")

def get_required_fields_for_job(job_data: Dict) -> List[str]:
    """Determine required profile fields based on job requirements"""
    base_required = [
        'full_name', 'email', 'phone', 'current_role', 
        'years_experience', 'programming_languages', 'degree'
    ]
    
    # Add location if job has location requirement
    if job_data.get('location'):
        base_required.append('location')
    
    # Add specific skills if mentioned in job
    job_skills = job_data.get('skills_required', [])
    if any('github' in skill.lower() for skill in job_skills):
        base_required.append('github_url')
    
    return base_required

def get_missing_profile_info(profile: PersonalProfile, required_fields: List[str] = None) -> List[str]:
    """Get list of missing required profile information"""
    if required_fields is None:
        required_fields = [
            'full_name', 'email', 'phone', 'current_role', 
            'years_experience', 'programming_languages', 'degree'
        ]
    
    missing_fields = []
    for field in required_fields:
        value = getattr(profile, field, None)
        if value is None or (isinstance(value, str) and value.strip() == ''):
            missing_fields.append(field)
    
    return missing_fields

def prompt_for_missing_info(missing_fields: List[str], profile: PersonalProfile) -> PersonalProfile:
    """Prompt user for missing profile information via terminal"""
    
    # Field descriptions for user-friendly prompts
    field_descriptions = {
        'full_name': 'Full Name',
        'email': 'Email Address',
        'phone': 'Phone Number',
        'location': 'Current Location (City, State, Country)',
        'linkedin_url': 'LinkedIn Profile URL',
        'github_url': 'GitHub Profile URL',
        'portfolio_url': 'Portfolio Website URL',
        'current_role': 'Current Job Title',
        'years_experience': 'Years of Experience (number)',
        'total_experience_months': 'Total Experience in Months (number)',
        'current_company': 'Current Company Name',
        'notice_period': 'Notice Period (e.g., 30 days, Immediate)',
        'expected_ctc': 'Expected CTC in LPA (number)',
        'current_ctc': 'Current CTC in LPA (number)',
        'programming_languages': 'Programming Languages (comma-separated)',
        'frameworks': 'Frameworks and Libraries (comma-separated)',
        'databases': 'Database Technologies (comma-separated)',
        'cloud_platforms': 'Cloud Platforms (comma-separated)',
        'tools': 'Tools and Technologies (comma-separated)',
        'other_skills': 'Other Relevant Skills (comma-separated)',
        'degree': 'Highest Degree (e.g., Bachelor of Technology)',
        'field_of_study': 'Field of Study (e.g., Computer Science)',
        'university': 'University/Institute Name',
        'graduation_year': 'Graduation Year (number)',
        'cgpa': 'CGPA/Grade (number)',
        'project_1_name': 'Project 1 Name',
        'project_1_description': 'Project 1 Description',
        'project_1_tech_stack': 'Project 1 Tech Stack',
        'project_1_github': 'Project 1 GitHub URL',
        'project_1_duration': 'Project 1 duration of work',
        'achievement_1': 'Achievement 1',
        'achievement_2': 'Achievement 2',
        'achievement_3': 'Achievement 3'
    }
    
    print("\\n" + "="*60)
    print("MISSING PROFILE INFORMATION")
    print("="*60)
    print("The following information is required for job applications:")
    print(f"Missing fields: {', '.join(missing_fields)}")
    print("\\nPlease provide the missing information:")
    print("-"*60)
    
    updated_profile_data = profile.dict()
    
    for field in missing_fields:
        description = field_descriptions.get(field, field.replace('_', ' ').title())
        
        while True:
            try:
                user_input = input(f"\\n{description}: ").strip()
                
                # Skip if user wants to leave it empty
                if user_input.lower() in ['skip', 'n/a', 'none', '']:
                    updated_profile_data[field] = None
                    break
                
                # Type conversion for numeric fields
                if field in ['years_experience', 'total_experience_months', 'graduation_year']:
                    updated_profile_data[field] = int(user_input)
                elif field in ['expected_ctc', 'current_ctc', 'cgpa']:
                    updated_profile_data[field] = float(user_input)
                else:
                    updated_profile_data[field] = user_input
                
                break
                
            except ValueError:
                print(f"Invalid input. Please enter a valid {field.replace('_', ' ')}")
            except KeyboardInterrupt:
                print("\\nOperation cancelled by user")
                return profile
    
    # Create updated profile
    try:
        updated_profile = PersonalProfile(**updated_profile_data)
        
        # Save to file
        updated_profile.save_to_file()
        
        print("\\n" + "="*60)
        print("PROFILE UPDATED SUCCESSFULLY")
        print("="*60)
        print(f"Updated information saved to {config.PERSONAL_PROFILE_PATH}")
        
        return updated_profile
        
    except ValidationError as e:
        logger.error(f"Profile validation error: {e}")
        print(f"\\nError updating profile: {e}")
        return profile

def interactive_profile_update():
    """Interactive profile update session"""
    print("\\n" + "="*60)
    print("INTERACTIVE PROFILE UPDATE")
    print("="*60)
    
    # Load current profile
    profile = PersonalProfile.load_from_file()
    
    # Show current profile status
    all_fields = list(profile.dict().keys())
    filled_fields = [field for field, value in profile.dict().items() if value is not None and str(value).strip() != '']
    empty_fields = [field for field in all_fields if field not in filled_fields]
    
    print(f"Current profile status:")
    print(f"- Filled fields: {len(filled_fields)}/{len(all_fields)}")
    print(f"- Empty fields: {len(empty_fields)}")
    
    if empty_fields:
        print(f"\\nEmpty fields: {', '.join(empty_fields[:10])}" + (" ..." if len(empty_fields) > 10 else ""))
        
        choice = input("\\nDo you want to fill in the missing information? (y/n): ").strip().lower()
        if choice == 'y':
            updated_profile = prompt_for_missing_info(empty_fields, profile)
            return updated_profile
    else:
        print("\\nProfile is complete!")
    
    return profile

def check_and_update_profile_for_job(job_data: Dict) -> PersonalProfile:
    """Check profile completeness for a specific job and update if needed"""
    profile = PersonalProfile.load_from_file()
    required_fields = get_required_fields_for_job(job_data)
    missing_fields = get_missing_profile_info(profile, required_fields)
    
    if missing_fields:
        print(f"\\n⚠️  Missing information for job application:")
        print(f"Job: {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown Company')}")
        
        updated_profile = prompt_for_missing_info(missing_fields, profile)
        return updated_profile
    
    return profile

# Telegram bot integration for remote updates (optional)
def send_telegram_prompt(missing_fields: List[str], job_data: Dict) -> bool:
    """Send Telegram message prompting for missing information (future implementation)"""
    # This would send a message to the user's Telegram bot asking for missing info
    # For now, we'll just log it
    logger.info(f"Would send Telegram prompt for missing fields: {missing_fields}")
    logger.info(f"For job: {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')}")
    return False  # Not implemented yet

# Example usage
# if __name__ == "__main__":
#     # Test loading profile
#     profile = PersonalProfile.load_from_file()
#     print(f"Loaded profile for: {profile.full_name}")
    
#     # Test checking missing info
#     missing = get_missing_profile_info(profile)
#     print(f"Missing fields: {missing}")
    
#     # Test interactive update
#     if missing:
#         choice = input("\\nRun interactive profile update? (y/n): ")
#         if choice.lower() == 'y':
#             updated_profile = interactive_profile_update()
#             print(f"Updated profile: {updated_profile.full_name}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("PROFILE LOAD TEST")
    print("="*60)

    # Load profile
    profile = PersonalProfile.load_from_file()

    print(f"\nLoaded profile for: {profile.full_name}")

    profile_dict = profile.dict()

    filled_fields = []
    empty_fields = []

    for field, value in profile_dict.items():
        if value is None or str(value).strip() == "":
            empty_fields.append(field)
        else:
            filled_fields.append(field)

    print("\nPROFILE SUMMARY")
    print("-"*60)
    print(f"Total fields: {len(profile_dict)}")
    print(f"Filled fields: {len(filled_fields)}")
    print(f"Empty fields: {len(empty_fields)}")

    print("\nFILLED FIELDS")
    print("-"*60)
    for field in filled_fields:
        print(f"{field}: {profile_dict[field]}")

    print("\nEMPTY FIELDS")
    print("-"*60)
    for field in empty_fields:
        print(field)

    # Check required fields
    missing = get_missing_profile_info(profile)

    print("\nREQUIRED FIELD CHECK")
    print("-"*60)
    if missing:
        print(f"Missing required fields: {missing}")
    else:
        print("All required fields are present ✅")

    # Optional interactive update
    if missing:
        choice = input("\nRun interactive profile update? (y/n): ")
        if choice.lower() == "y":
            updated_profile = interactive_profile_update()
            print(f"\nUpdated profile name: {updated_profile.full_name}")
"""
Automator Module
Handles web-based applications using Playwright and email-based applications using smtplib
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Optional, List
from datetime import datetime
import re
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
import aiofiles

from config import config

logger = logging.getLogger(__name__)

class WebAutomator:
    """Handles web-based job applications using Playwright"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context = None
        self.page: Optional[Page] = None
        
    async def start_browser(self, headless: bool = True):
        """Start Playwright browser"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run',
                    '--disable-default-apps',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            # Create context with stealth settings
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720},
                java_script_enabled=True
            )
            
            self.page = await self.context.new_page()
            
            # Add stealth scripts
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                window.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            logger.info("Browser started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise
    
    async def close_browser(self):
        """Close Playwright browser"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    async def apply_to_job_generic(self, job_data: Dict, cv_path: str, profile_data: Dict) -> Dict:
        """Generic job application handler"""
        application_url = job_data.get('application_url')
        
        if not application_url:
            logger.error("No application URL found in job data")
            return {'status': 'failed', 'reason': 'No application URL'}
        
        try:
            await self.page.goto(application_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)  # Wait for page to fully load
            
            # Take screenshot for debugging
            screenshot_path = config.LOGS_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=screenshot_path)
            
            # Detect the type of application portal
            page_content = await self.page.content()
            
            if 'workday' in page_content.lower() or 'workday' in application_url.lower():
                return await self.handle_workday_application(job_data, cv_path, profile_data)
            elif 'naukri' in page_content.lower() or 'naukri' in application_url.lower():
                return await self.handle_naukri_application(job_data, cv_path, profile_data)
            elif 'linkedin' in page_content.lower() or 'linkedin' in application_url.lower():
                return await self.handle_linkedin_application(job_data, cv_path, profile_data)
            else:
                return await self.handle_generic_application_form(job_data, cv_path, profile_data)
        
        except Exception as e:
            logger.error(f"Error in generic job application: {e}")
            return {'status': 'failed', 'reason': str(e)}
    
    async def handle_workday_application(self, job_data: Dict, cv_path: str, profile_data: Dict) -> Dict:
        """Handle Workday-based applications"""
        try:
            logger.info("Handling Workday application")
            
            # Wait for Workday to load
            await self.page.wait_for_selector('[data-automation-id]', timeout=10000)
            
            # Click Apply button
            apply_selectors = [
                '[data-automation-id*="apply"]',
                'button:has-text("Apply")',
                'a:has-text("Apply")',
                '[aria-label*="Apply"]'
            ]
            
            apply_clicked = False
            for selector in apply_selectors:
                try:
                    await self.page.click(selector, timeout=5000)
                    apply_clicked = True
                    logger.info(f"Clicked apply button with selector: {selector}")
                    break
                except:
                    continue
            
            if not apply_clicked:
                return {'status': 'failed', 'reason': 'Could not find Apply button'}
            
            await asyncio.sleep(3)
            
            # Fill in personal information
            await self._fill_workday_personal_info(profile_data)
            
            # Upload CV
            await self._upload_cv_workday(cv_path)
            
            # Handle additional questions
            await self._handle_workday_questions(job_data)
            
            # Submit application (with confirmation)
            if config.AUTO_APPLY:
                await self._submit_workday_application()
                return {'status': 'submitted', 'platform': 'Workday'}
            else:
                return {'status': 'ready_to_submit', 'platform': 'Workday', 'message': 'Application filled but not submitted (AUTO_APPLY=false)'}
        
        except Exception as e:
            logger.error(f"Error in Workday application: {e}")
            return {'status': 'failed', 'reason': f'Workday error: {str(e)}'}
    
    async def _fill_workday_personal_info(self, profile_data: Dict):
        """Fill personal information in Workday forms"""
        field_mappings = {
            'input[data-automation-id*="firstName"]': profile_data.get('full_name', '').split()[0] if profile_data.get('full_name') else '',
            'input[data-automation-id*="lastName"]': ' '.join(profile_data.get('full_name', '').split()[1:]) if profile_data.get('full_name') else '',
            'input[data-automation-id*="email"]': profile_data.get('email', ''),
            'input[data-automation-id*="phone"]': profile_data.get('phone', ''),
            'input[data-automation-id*="address"]': profile_data.get('location', ''),
        }
        
        for selector, value in field_mappings.items():
            if value:
                try:
                    await self.page.fill(selector, value, timeout=5000)
                    logger.info(f"Filled {selector} with {value}")
                except:
                    logger.warning(f"Could not fill {selector}")
    
    async def _upload_cv_workday(self, cv_path: str):
        """Upload CV in Workday"""
        upload_selectors = [
            'input[type="file"]',
            '[data-automation-id*="file"]',
            '[data-automation-id*="upload"]',
            '[data-automation-id*="resume"]'
        ]
        
        for selector in upload_selectors:
            try:
                await self.page.set_input_files(selector, cv_path, timeout=5000)
                logger.info(f"Uploaded CV using selector: {selector}")
                await asyncio.sleep(2)  # Wait for upload to process
                return
            except:
                continue
        
        logger.warning("Could not upload CV to Workday")
    
    async def _handle_workday_questions(self, job_data: Dict):
        """Handle additional questions in Workday"""
        # Common Workday questions and responses
        try:
            # Sponsorship question
            sponsorship_selectors = [
                'input[value*="No"][data-automation-id*="sponsorship"]',
                'input[value*="false"][data-automation-id*="sponsorship"]'
            ]
            
            for selector in sponsorship_selectors:
                try:
                    await self.page.click(selector, timeout=3000)
                    break
                except:
                    continue
            
            # Experience dropdown
            experience_years = str(job_data.get('experience_min', 2))
            experience_selectors = [
                f'option:has-text("{experience_years}")',
                f'[data-automation-id*="experience"] option[value*="{experience_years}"]'
            ]
            
            for selector in experience_selectors:
                try:
                    await self.page.click(selector, timeout=3000)
                    break
                except:
                    continue
            
        except Exception as e:
            logger.warning(f"Error handling Workday questions: {e}")
    
    async def _submit_workday_application(self):
        """Submit Workday application"""
        submit_selectors = [
            'button[data-automation-id*="submit"]',
            'button:has-text("Submit")',
            'input[type="submit"]',
            '[data-automation-id*="submitApplication"]'
        ]
        
        for selector in submit_selectors:
            try:
                await self.page.click(selector, timeout=5000)
                logger.info("Submitted Workday application")
                return
            except:
                continue
        
        logger.warning("Could not submit Workday application")
    
    async def handle_naukri_application(self, job_data: Dict, cv_path: str, profile_data: Dict) -> Dict:
        """Handle Naukri.com applications"""
        try:
            logger.info("Handling Naukri application")
            
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Look for login requirement
            if await self.page.locator('text="Login"').count() > 0:
                logger.error("Naukri requires login")
                return {'status': 'failed', 'reason': 'Login required for Naukri'}
            
            # Click apply button
            apply_selectors = [
                'button:has-text("Apply")',
                '.apply-button',
                '#apply-button',
                'a:has-text("Apply Now")'
            ]
            
            apply_clicked = False
            for selector in apply_selectors:
                try:
                    await self.page.click(selector, timeout=5000)
                    apply_clicked = True
                    break
                except:
                    continue
            
            if not apply_clicked:
                return {'status': 'failed', 'reason': 'Could not find Apply button on Naukri'}
            
            return {'status': 'submitted', 'platform': 'Naukri'}
        
        except Exception as e:
            logger.error(f"Error in Naukri application: {e}")
            return {'status': 'failed', 'reason': f'Naukri error: {str(e)}'}
    
    async def handle_linkedin_application(self, job_data: Dict, cv_path: str, profile_data: Dict) -> Dict:
        """Handle LinkedIn applications"""
        try:
            logger.info("Handling LinkedIn application")
            
            # LinkedIn requires login
            if await self.page.locator('text="Sign in"').count() > 0:
                logger.error("LinkedIn requires login")
                return {'status': 'failed', 'reason': 'Login required for LinkedIn'}
            
            # Easy Apply button
            if await self.page.locator('button:has-text("Easy Apply")').count() > 0:
                await self.page.click('button:has-text("Easy Apply")')
                
                # Handle Easy Apply flow
                await self._handle_linkedin_easy_apply(cv_path, profile_data)
                
                return {'status': 'submitted', 'platform': 'LinkedIn'}
            else:
                return {'status': 'failed', 'reason': 'No Easy Apply option on LinkedIn'}
        
        except Exception as e:
            logger.error(f"Error in LinkedIn application: {e}")
            return {'status': 'failed', 'reason': f'LinkedIn error: {str(e)}'}
    
    async def _handle_linkedin_easy_apply(self, cv_path: str, profile_data: Dict):
        """Handle LinkedIn Easy Apply flow"""
        max_steps = 5
        current_step = 0
        
        while current_step < max_steps:
            try:
                # Check for Next or Submit button
                if await self.page.locator('button:has-text("Submit application")').count() > 0:
                    if config.AUTO_APPLY:
                        await self.page.click('button:has-text("Submit application")')
                        logger.info("Submitted LinkedIn Easy Apply")
                    break
                elif await self.page.locator('button:has-text("Next")').count() > 0:
                    await self.page.click('button:has-text("Next")')
                    current_step += 1
                    await asyncio.sleep(2)
                else:
                    break
            except:
                break
    
    async def handle_generic_application_form(self, job_data: Dict, cv_path: str, profile_data: Dict) -> Dict:
        """Handle generic application forms"""
        try:
            logger.info("Handling generic application form")
            
            # Look for common form fields and fill them
            await self._fill_generic_form_fields(profile_data)
            
            # Try to upload CV
            await self._upload_cv_generic(cv_path)
            
            # Look for submit button
            if config.AUTO_APPLY:
                await self._submit_generic_form()
                return {'status': 'submitted', 'platform': 'Generic'}
            else:
                return {'status': 'ready_to_submit', 'platform': 'Generic'}
        
        except Exception as e:
            logger.error(f"Error in generic application: {e}")
            return {'status': 'failed', 'reason': f'Generic form error: {str(e)}'}
    
    async def _fill_generic_form_fields(self, profile_data: Dict):
        """Fill common form fields in generic applications"""
        # Common field selectors and their corresponding data
        field_mappings = [
            ('input[name*="name"], input[id*="name"], input[placeholder*="name"]', profile_data.get('full_name', '')),
            ('input[name*="email"], input[id*="email"], input[type="email"]', profile_data.get('email', '')),
            ('input[name*="phone"], input[id*="phone"], input[type="tel"]', profile_data.get('phone', '')),
            ('textarea[name*="cover"], textarea[id*="cover"]', f"Dear Hiring Manager,\\n\\nI am interested in the {job_data.get('title', 'position')} role at your company.\\n\\nBest regards,\\n{profile_data.get('full_name', '')}"),
        ]
        
        for selector, value in field_mappings:
            if value:
                try:
                    await self.page.fill(selector, str(value), timeout=3000)
                    logger.info(f"Filled field with selector: {selector}")
                except:
                    logger.debug(f"Could not fill field: {selector}")
    
    async def _upload_cv_generic(self, cv_path: str):
        """Upload CV in generic forms"""
        upload_selectors = [
            'input[type="file"]',
            'input[name*="resume"]',
            'input[name*="cv"]',
            'input[id*="resume"]',
            'input[id*="cv"]'
        ]
        
        for selector in upload_selectors:
            try:
                await self.page.set_input_files(selector, cv_path, timeout=5000)
                logger.info(f"Uploaded CV using selector: {selector}")
                await asyncio.sleep(2)
                return
            except:
                continue
        
        logger.warning("Could not upload CV to generic form")
    
    async def _submit_generic_form(self):
        """Submit generic application form"""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send")',
            '.submit-button',
            '#submit'
        ]
        
        for selector in submit_selectors:
            try:
                await self.page.click(selector, timeout=5000)
                logger.info("Submitted generic application form")
                return
            except:
                continue
        
        logger.warning("Could not submit generic application form")

class EmailAutomator:
    """Handles email-based job applications"""
    
    def __init__(self):
        self.smtp_server = config.SMTP_SERVER
        self.smtp_port = config.SMTP_PORT
        self.email_user = config.EMAIL_USER
        self.email_password = config.EMAIL_PASSWORD
    
    def send_application_email(self, job_data: Dict, cv_path: str, profile_data: Dict) -> Dict:
        """Send job application via email"""
        try:
            application_email = job_data.get('application_email')
            if not application_email:
                return {'status': 'failed', 'reason': 'No application email provided'}
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = application_email
            msg['Subject'] = self._create_email_subject(job_data)
            
            # Create email body
            body = self._create_email_body(job_data, profile_data)
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach CV
            if cv_path and Path(cv_path).exists():
                with open(cv_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {Path(cv_path).name}',
                )
                
                msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            
            text = msg.as_string()
            server.sendmail(self.email_user, application_email, text)
            server.quit()
            
            logger.info(f"Application email sent to {application_email}")
            return {'status': 'sent', 'platform': 'Email', 'recipient': application_email}
        
        except Exception as e:
            logger.error(f"Error sending application email: {e}")
            return {'status': 'failed', 'reason': f'Email error: {str(e)}'}
    
    def _create_email_subject(self, job_data: Dict) -> str:
        """Create email subject line"""
        job_title = job_data.get('title', 'Software Developer')
        company = job_data.get('company', '')
        
        if company:
            return f"Application for {job_title} position at {company}"
        else:
            return f"Application for {job_title} position"
    
    def _create_email_body(self, job_data: Dict, profile_data: Dict) -> str:
        """Create email body"""
        job_title = job_data.get('title', 'the position')
        company = job_data.get('company', 'your organization')
        candidate_name = profile_data.get('full_name', 'Candidate')
        
        body = f"""Dear Hiring Manager,

I hope this email finds you well. I am writing to express my strong interest in the {job_title} position at {company}.

With {profile_data.get('years_experience', 'several')} years of experience in software development, I am confident that my skills and expertise align well with the requirements of this role.

Key highlights of my background:
- Proficient in: {profile_data.get('programming_languages', 'various programming languages')}
- Experience with: {profile_data.get('frameworks', 'modern frameworks and technologies')}
- Current role: {profile_data.get('current_role', 'Software Developer')} at {profile_data.get('current_company', 'my current organization')}

I have attached my resume for your review and would welcome the opportunity to discuss how my experience and enthusiasm can contribute to your team's success.

Thank you for considering my application. I look forward to hearing from you.

Best regards,
{candidate_name}
Phone: {profile_data.get('phone', '')}
Email: {profile_data.get('email', '')}
LinkedIn: {profile_data.get('linkedin_url', '')}
"""
        
        return body

class ApplicationAutomator:
    """Main automator class that coordinates web and email applications"""
    
    def __init__(self):
        self.web_automator = WebAutomator()
        self.email_automator = EmailAutomator()
    
    async def apply_to_job(self, job_data: Dict, cv_path: str, profile_data: Dict) -> Dict:
        """Apply to a job using the appropriate method"""
        
        # Check if we have an application URL (web-based)
        if job_data.get('application_url'):
            try:
                await self.web_automator.start_browser(headless=True)
                result = await self.web_automator.apply_to_job_generic(job_data, cv_path, profile_data)
                await self.web_automator.close_browser()
                return result
            except Exception as e:
                logger.error(f"Web application failed: {e}")
                await self.web_automator.close_browser()
                
                # Fallback to email if available
                if job_data.get('application_email'):
                    return self.email_automator.send_application_email(job_data, cv_path, profile_data)
                else:
                    return {'status': 'failed', 'reason': f'Web application failed: {str(e)}'}
        
        # Check if we have an application email
        elif job_data.get('application_email'):
            return self.email_automator.send_application_email(job_data, cv_path, profile_data)
        
        else:
            return {'status': 'failed', 'reason': 'No application URL or email provided'}
    
    async def batch_apply_jobs(self, jobs_with_cvs: List[Dict]) -> List[Dict]:
        """Apply to multiple jobs"""
        results = []
        
        for job_cv_data in jobs_with_cvs:
            try:
                job_data = job_cv_data['job_data']
                cv_path = job_cv_data['cv_path']
                profile_data = job_cv_data['profile_data']
                
                logger.info(f"Applying to: {job_data.get('title', 'Unknown')} at {job_data.get('company', 'Unknown')}")
                
                result = await self.apply_to_job(job_data, cv_path, profile_data)
                result.update({
                    'job_title': job_data.get('title'),
                    'company': job_data.get('company'),
                    'applied_at': datetime.now().isoformat()
                })
                
                results.append(result)
                
                # Delay between applications
                if config.DELAY_BETWEEN_APPLICATIONS > 0:
                    await asyncio.sleep(config.DELAY_BETWEEN_APPLICATIONS)
                
            except Exception as e:
                logger.error(f"Error applying to job: {e}")
                results.append({
                    'status': 'failed',
                    'reason': str(e),
                    'job_title': job_data.get('title', 'Unknown'),
                    'company': job_data.get('company', 'Unknown'),
                    'applied_at': datetime.now().isoformat()
                })
        
        return results

# Example usage and testing
async def test_automator():
    """Test automator functionality"""
    job_data = {
        'title': 'Software Developer',
        'company': 'Test Company',
        'application_url': 'https://example.com/apply',
        'application_email': 'careers@example.com'
    }
    
    profile_data = {
        'full_name': 'John Doe',
        'email': 'john.doe@email.com',
        'phone': '+1234567890',
        'years_experience': 3
    }
    
    automator = ApplicationAutomator()
    
    # Test email application
    result = automator.email_automator.send_application_email(job_data, None, profile_data)
    print(f"Email application result: {result}")

if __name__ == "__main__":
    asyncio.run(test_automator())
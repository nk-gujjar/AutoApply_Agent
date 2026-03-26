"""
Main Orchestrator for AutoApply Agent
Coordinates all modules to provide the complete job application automation pipeline
"""

import asyncio
import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
import sys
from pathlib import Path

# Import all modules
from config import config, logger
from scraper import TelegramScraper
from processor import JobProcessor
from cv_engine import CVEngine
from automator import ApplicationAutomator
from human_loop import PersonalProfile, check_and_update_profile_for_job, get_missing_profile_info
from tracker import ApplicationTracker, track_batch_applications

class AutoApplyAgent:
    """Main orchestrator for the AutoApply Agent"""
    
    def __init__(self):
        self.scraper = TelegramScraper()
        self.processor = JobProcessor()
        self.cv_engine = CVEngine()
        self.automator = ApplicationAutomator()
        self.tracker = ApplicationTracker()
        
        self.daily_application_count = 0
        self.profile = None
        
        logger.info("AutoApply Agent initialized")
    
    async def initialize(self) -> bool:
        """Initialize all components and validate configuration"""
        try:
            # Validate configuration
            missing_configs = config.validate_config()
            if missing_configs:
                logger.error(f"Missing required configuration: {', '.join(missing_configs)}")
                print(f"❌ Missing configuration values: {', '.join(missing_configs)}")
                print("Please update your .env file with the required values.")
                return False
            
            # Load and validate profile
            self.profile = PersonalProfile.load_from_file()
            missing_profile_info = get_missing_profile_info(self.profile)
            
            if missing_profile_info:
                logger.warning(f"Missing profile information: {', '.join(missing_profile_info)}")
                print(f"⚠️  Missing profile information: {', '.join(missing_profile_info)}")
                
                choice = input("\\nDo you want to fill in the missing information now? (y/n): ").strip().lower()
                if choice == 'y':
                    from human_loop import interactive_profile_update
                    self.profile = interactive_profile_update()
                else:
                    print("You can update your profile later using the --update-profile option")
            
            # Initialize Telegram scraper
            if not await self.scraper.connect():
                logger.error("Failed to connect to Telegram")
                return False
            
            # Get today's application count
            today_stats = self.tracker.get_application_stats()
            self.daily_application_count = today_stats.get('applications_today', 0)
            
            logger.info("AutoApply Agent initialized successfully")
            print("✅ AutoApply Agent initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing AutoApply Agent: {e}")
            print(f"❌ Error initializing: {e}")
            return False
    
    async def run_batch_job_search(self, days_back: int = 7) -> List[Dict]:
        """Run batch job search on historical messages"""
        try:
            logger.info(f"Starting batch job search for last {days_back} days")
            print(f"🔍 Searching for jobs from last {days_back} days...")
            
            # Scrape jobs from all channels
            raw_jobs = await self.scraper.run_batch_scraping(days_back)
            
            if not raw_jobs:
                logger.info("No jobs found in batch scraping")
                print("ℹ️  No jobs found matching your criteria")
                return []
            
            print(f"📊 Found {len(raw_jobs)} potential job postings")
            logger.info(f"Found {len(raw_jobs)} raw job postings")
            
            # Process jobs with AI
            print("🤖 Processing job descriptions with AI...")
            processed_jobs = await self.processor.process_batch_jobs(raw_jobs)
            
            if not processed_jobs:
                logger.info("No jobs processed successfully")
                print("ℹ️  No jobs could be processed")
                return []
            
            # Filter jobs by criteria
            filtered_jobs = self.processor.filter_jobs_by_criteria(processed_jobs)
            
            print(f"✅ Processed and filtered {len(filtered_jobs)} jobs")
            logger.info(f"Filtered to {len(filtered_jobs)} jobs matching criteria")
            
            # Save processed jobs
            if filtered_jobs:
                jobs_file = await self.processor.save_processed_jobs(filtered_jobs, "batch_jobs.json")
                print(f"💾 Saved processed jobs to {jobs_file}")
            
            return filtered_jobs
            
        except Exception as e:
            logger.error(f"Error in batch job search: {e}")
            print(f"❌ Error in batch job search: {e}")
            return []
    
    async def process_jobs_for_application(self, jobs: List[Dict]) -> List[Dict]:
        """Process jobs and generate CVs"""
        jobs_with_cvs = []
        
        print(f"📝 Generating tailored CVs for {len(jobs)} jobs...")
        
        for i, job in enumerate(jobs, 1):
            try:
                print(f"\\n[{i}/{len(jobs)}] Processing: {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
                
                # Check if profile is complete for this job
                updated_profile = check_and_update_profile_for_job(job)
                
                # Generate CV
                cv_path = await self.cv_engine.generate_cv_for_job(job)
                
                if cv_path:
                    jobs_with_cvs.append({
                        'job_data': job,
                        'cv_path': cv_path,
                        'profile_data': updated_profile.dict()
                    })
                    print(f"✅ Generated CV: {Path(cv_path).name}")
                else:
                    print(f"❌ Failed to generate CV")
                    logger.warning(f"Failed to generate CV for {job.get('title')} at {job.get('company')}")
                
            except Exception as e:
                logger.error(f"Error processing job for CV generation: {e}")
                print(f"❌ Error processing job: {e}")
                continue
        
        print(f"\\n📝 Successfully generated {len(jobs_with_cvs)} CVs")
        return jobs_with_cvs
    
    async def apply_to_jobs(self, jobs_with_cvs: List[Dict]) -> List[Dict]:
        """Apply to jobs using the automator"""
        
        if self.daily_application_count >= config.MAX_APPLICATIONS_PER_DAY:
            logger.warning(f"Daily application limit reached: {self.daily_application_count}")
            print(f"⚠️  Daily application limit reached ({config.MAX_APPLICATIONS_PER_DAY})")
            return []
        
        # Calculate how many more applications we can send today
        remaining_applications = config.MAX_APPLICATIONS_PER_DAY - self.daily_application_count
        jobs_to_apply = jobs_with_cvs[:remaining_applications]
        
        if len(jobs_with_cvs) > remaining_applications:
            print(f"⚠️  Limiting to {remaining_applications} applications due to daily limit")
        
        print(f"🚀 Applying to {len(jobs_to_apply)} jobs...")
        
        # Apply to jobs
        application_results = await self.automator.batch_apply_jobs(jobs_to_apply)
        
        # Combine results
        jobs_with_results = []
        for i, result in enumerate(application_results):
            jobs_with_results.append({
                'job_data': jobs_to_apply[i]['job_data'],
                'cv_path': jobs_to_apply[i]['cv_path'],
                'profile_data': jobs_to_apply[i]['profile_data'],
                'application_result': result
            })
        
        # Track applications
        print("📊 Recording applications in tracker...")
        track_batch_applications(jobs_with_results, self.tracker)
        
        # Print results summary
        successful = len([r for r in application_results if r['status'] in ['submitted', 'sent']])
        failed = len([r for r in application_results if r['status'] == 'failed'])
        
        print(f"\\n📈 Application Results:")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        
        return jobs_with_results
    
    async def run_full_pipeline(self, days_back: int = 7) -> Dict:
        """Run the complete job search and application pipeline"""
        try:
            start_time = datetime.now()
            print("\\n" + "="*60)
            print("🤖 AUTOAPPLY AGENT - FULL PIPELINE")
            print("="*60)
            
            # Step 1: Search for jobs
            jobs = await self.run_batch_job_search(days_back)
            if not jobs:
                return {'status': 'no_jobs_found', 'message': 'No jobs found matching criteria'}
            
            # Step 2: Generate CVs
            jobs_with_cvs = await self.process_jobs_for_application(jobs)
            if not jobs_with_cvs:
                return {'status': 'no_cvs_generated', 'message': 'No CVs could be generated'}
            
            # Step 3: Apply to jobs
            results = await self.apply_to_jobs(jobs_with_cvs)
            
            # Step 4: Generate summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            summary = {
                'status': 'completed',
                'duration_seconds': duration,
                'jobs_found': len(jobs),
                'cvs_generated': len(jobs_with_cvs),
                'applications_attempted': len(results),
                'successful_applications': len([r for r in results if r['application_result']['status'] in ['submitted', 'sent']]),
                'failed_applications': len([r for r in results if r['application_result']['status'] == 'failed']),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
            print(f"\\n⏱️  Pipeline completed in {duration:.1f} seconds")
            print("="*60)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error in full pipeline: {e}")
            print(f"❌ Pipeline failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def run_monitoring_mode(self):
        """Run continuous monitoring for new job postings"""
        try:
            logger.info("Starting monitoring mode")
            print("\\n👁️  Starting real-time monitoring mode...")
            print("Press Ctrl+C to stop monitoring")
            
            # Setup real-time monitoring
            await self.scraper.setup_real_time_monitoring(config.TARGET_CHANNELS)
            
            # Keep running
            await self.scraper.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            print("\\n⏹️  Monitoring stopped by user")
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in monitoring mode: {e}")
            print(f"❌ Monitoring error: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.scraper.disconnect()
            logger.info("AutoApply Agent cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def print_stats():
    """Print current application statistics"""
    tracker = ApplicationTracker()
    stats = tracker.get_application_stats()
    
    print("\\n📊 Current Statistics:")
    print(f"Total Applications: {stats.get('total_applications', 0)}")
    print(f"Applications Today: {stats.get('applications_today', 0)}")
    print(f"Success Rate: {stats.get('success_rate', 0):.1f}%")
    
    if stats.get('status_breakdown'):
        print("\\nStatus Breakdown:")
        for status, count in stats['status_breakdown'].items():
            print(f"  {status.title()}: {count}")

def generate_report():
    """Generate and display application report"""
    tracker = ApplicationTracker()
    report_path = tracker.generate_report()
    print(f"📋 Report generated: {report_path}")

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoApply Agent - Automated Job Application System")
    parser.add_argument('--mode', choices=['batch', 'monitor', 'stats', 'report', 'update-profile'], 
                       default='batch', help='Operation mode')
    parser.add_argument('--days', type=int, default=7, help='Days back to search for jobs (batch mode)')
    parser.add_argument('--headless', action='store_true', default=True, help='Run browser in headless mode')
    
    args = parser.parse_args()
    
    if args.mode == 'stats':
        print_stats()
        return
    
    if args.mode == 'report':
        generate_report()
        return
    
    if args.mode == 'update-profile':
        from human_loop import interactive_profile_update
        interactive_profile_update()
        return
    
    # Initialize agent
    agent = AutoApplyAgent()
    
    try:
        if not await agent.initialize():
            print("❌ Failed to initialize AutoApply Agent")
            sys.exit(1)
        
        if args.mode == 'batch':
            await agent.run_full_pipeline(args.days)
        elif args.mode == 'monitor':
            await agent.run_monitoring_mode()
        
    except KeyboardInterrupt:
        print("\\n⏹️  Operation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Unexpected error: {e}")
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    # Set up asyncio event loop policy for compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\nGoodbye! 👋")
"""
Tracker Module
Tracks job applications and maintains application history
Stores data in both CSV and TXT formats for easy access
"""

import csv
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd

from config import config

logger = logging.getLogger(__name__)

class ApplicationTracker:
    """Track job applications and maintain history"""
    
    def __init__(self):
        self.csv_path = config.TRACKER_CSV_PATH
        self.txt_path = config.HISTORY_TXT_PATH
        self.json_path = config.DATA_DIR / "applications.json"
        
        # Initialize files if they don't exist
        self._initialize_files()
    
    def _initialize_files(self):
        """Initialize tracking files if they don't exist"""
        
        # Initialize CSV file
        if not self.csv_path.exists():
            headers = [
                'application_id', 'date', 'job_title', 'company', 'location',
                'application_url', 'application_email', 'cv_path', 'status',
                'platform', 'source_channel', 'message_id', 'message_link',
                'applied_at', 'response_received', 'response_date', 'notes'
            ]
            
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            
            logger.info(f"Created CSV tracker file: {self.csv_path}")
        
        # Initialize TXT file
        if not self.txt_path.exists():
            with open(self.txt_path, 'w') as f:
                f.write("AutoApply Agent - Job Application History\\n")
                f.write("="*50 + "\\n\\n")
            
            logger.info(f"Created TXT history file: {self.txt_path}")
        
        # Initialize JSON file
        if not self.json_path.exists():
            with open(self.json_path, 'w') as f:
                json.dump([], f, indent=2)
            
            logger.info(f"Created JSON applications file: {self.json_path}")
    
    def add_application(self, job_data: Dict, cv_path: str, application_result: Dict, profile_data: Dict = None) -> str:
        """Add a new job application to tracking"""
        
        # Generate unique application ID
        app_id = self._generate_application_id(job_data)
        
        # Prepare application data
        app_data = {
            'application_id': app_id,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'job_title': job_data.get('title', 'Unknown'),
            'company': job_data.get('company', 'Unknown'),
            'location': job_data.get('location', ''),
            'application_url': job_data.get('application_url', ''),
            'application_email': job_data.get('application_email', ''),
            'cv_path': cv_path,
            'status': application_result.get('status', 'unknown'),
            'platform': application_result.get('platform', ''),
            'source_channel': job_data.get('source_channel', ''),
            'message_id': job_data.get('message_id', ''),
            'message_link': job_data.get('message_link', ''),
            'applied_at': datetime.now().isoformat(),
            'response_received': '',
            'response_date': '',
            'notes': application_result.get('reason', '')
        }
        
        # Add to CSV
        self._add_to_csv(app_data)
        
        # Add to TXT
        self._add_to_txt(app_data)
        
        # Add to JSON
        self._add_to_json(app_data, job_data, application_result, profile_data)
        
        logger.info(f"Added application to tracker: {app_id}")
        return app_id
    
    def _generate_application_id(self, job_data: Dict) -> str:
        """Generate unique application ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        company = job_data.get('company', 'unknown').replace(' ', '').lower()[:10]
        title = job_data.get('title', 'unknown').replace(' ', '').lower()[:10]
        
        return f"{timestamp}_{company}_{title}"
    
    def _add_to_csv(self, app_data: Dict):
        """Add application to CSV file"""
        try:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=app_data.keys())
                writer.writerow(app_data)
        except Exception as e:
            logger.error(f"Error adding to CSV: {e}")
    
    def _add_to_txt(self, app_data: Dict):
        """Add application to TXT history file"""
        try:
            with open(self.txt_path, 'a') as f:
                f.write(f"Application ID: {app_data['application_id']}\\n")
                f.write(f"Date: {app_data['date']}\\n")
                f.write(f"Job: {app_data['job_title']} at {app_data['company']}\\n")
                f.write(f"Location: {app_data['location']}\\n")
                f.write(f"Status: {app_data['status']}\\n")
                f.write(f"Platform: {app_data['platform']}\\n")
                f.write(f"CV Path: {app_data['cv_path']}\\n")
                f.write(f"Source: {app_data['source_channel']}\\n")
                f.write(f"Applied At: {app_data['applied_at']}\\n")
                
                if app_data['notes']:
                    f.write(f"Notes: {app_data['notes']}\\n")
                
                f.write("-" * 50 + "\\n\\n")
        except Exception as e:
            logger.error(f"Error adding to TXT: {e}")
    
    def _add_to_json(self, app_data: Dict, job_data: Dict, application_result: Dict, profile_data: Dict = None):
        """Add application to JSON file with full details"""
        try:
            # Load existing data
            applications = []
            if self.json_path.exists():
                with open(self.json_path, 'r') as f:
                    applications = json.load(f)
            
            # Create detailed application record
            detailed_record = {
                'application_data': app_data,
                'job_data': job_data,
                'application_result': application_result,
                'profile_data': profile_data,
                'created_at': datetime.now().isoformat()
            }
            
            applications.append(detailed_record)
            
            # Save updated data
            with open(self.json_path, 'w') as f:
                json.dump(applications, f, indent=2)
        except Exception as e:
            logger.error(f"Error adding to JSON: {e}")
    
    def update_application_status(self, app_id: str, status: str, notes: str = "") -> bool:
        """Update application status"""
        try:
            # Update CSV
            self._update_csv_status(app_id, status, notes)
            
            # Update JSON
            self._update_json_status(app_id, status, notes)
            
            # Add to TXT history
            with open(self.txt_path, 'a') as f:
                f.write(f"UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
                f.write(f"Application ID: {app_id}\\n")
                f.write(f"New Status: {status}\\n")
                if notes:
                    f.write(f"Notes: {notes}\\n")
                f.write("-" * 30 + "\\n\\n")
            
            logger.info(f"Updated application status: {app_id} -> {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating application status: {e}")
            return False
    
    def _update_csv_status(self, app_id: str, status: str, notes: str):
        """Update status in CSV file"""
        try:
            # Read current CSV
            df = pd.read_csv(self.csv_path)
            
            # Update the specific row
            mask = df['application_id'] == app_id
            if mask.any():
                df.loc[mask, 'status'] = status
                df.loc[mask, 'response_received'] = 'Yes' if status in ['interview', 'offer', 'rejected'] else ''
                df.loc[mask, 'response_date'] = datetime.now().strftime('%Y-%m-%d') if status in ['interview', 'offer', 'rejected'] else ''
                if notes:
                    df.loc[mask, 'notes'] = notes
                
                # Save updated CSV
                df.to_csv(self.csv_path, index=False)
            else:
                logger.warning(f"Application ID {app_id} not found in CSV")
        except Exception as e:
            logger.error(f"Error updating CSV status: {e}")
    
    def _update_json_status(self, app_id: str, status: str, notes: str):
        """Update status in JSON file"""
        try:
            with open(self.json_path, 'r') as f:
                applications = json.load(f)
            
            # Find and update the application
            for app in applications:
                if app.get('application_data', {}).get('application_id') == app_id:
                    app['application_data']['status'] = status
                    app['application_data']['response_date'] = datetime.now().isoformat()
                    if notes:
                        app['application_data']['notes'] = notes
                    app['last_updated'] = datetime.now().isoformat()
                    break
            
            # Save updated data
            with open(self.json_path, 'w') as f:
                json.dump(applications, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating JSON status: {e}")
    
    def get_application_stats(self) -> Dict:
        """Get application statistics"""
        try:
            df = pd.read_csv(self.csv_path)
            
            stats = {
                'total_applications': len(df),
                'applications_today': len(df[df['date'] == datetime.now().strftime('%Y-%m-%d')]),
                'status_breakdown': df['status'].value_counts().to_dict(),
                'platform_breakdown': df['platform'].value_counts().to_dict(),
                'companies_applied': df['company'].nunique(),
                'success_rate': 0
            }
            
            # Calculate success rate
            successful_statuses = ['interview', 'offer', 'hired']
            successful_apps = len(df[df['status'].isin(successful_statuses)])
            if stats['total_applications'] > 0:
                stats['success_rate'] = (successful_apps / stats['total_applications']) * 100
            
            return stats
        except Exception as e:
            logger.error(f"Error getting application stats: {e}")
            return {}
    
    def get_recent_applications(self, days: int = 7) -> List[Dict]:
        """Get recent applications"""
        try:
            df = pd.read_csv(self.csv_path)
            
            # Convert date column to datetime
            df['date'] = pd.to_datetime(df['date'])
            
            # Filter recent applications
            cutoff_date = datetime.now() - pd.Timedelta(days=days)
            recent_df = df[df['date'] >= cutoff_date]
            
            return recent_df.to_dict('records')
        except Exception as e:
            logger.error(f"Error getting recent applications: {e}")
            return []
    
    def search_applications(self, company: str = None, status: str = None, job_title: str = None) -> List[Dict]:
        """Search applications by criteria"""
        try:
            df = pd.read_csv(self.csv_path)
            
            # Apply filters
            if company:
                df = df[df['company'].str.contains(company, case=False, na=False)]
            if status:
                df = df[df['status'] == status]
            if job_title:
                df = df[df['job_title'].str.contains(job_title, case=False, na=False)]
            
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error searching applications: {e}")
            return []
    
    def export_data(self, format: str = 'csv', filename: str = None) -> str:
        """Export application data to different formats"""
        try:
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"applications_export_{timestamp}"
            
            output_path = config.OUTPUT_DIR / f"{filename}.{format}"
            
            if format.lower() == 'csv':
                # Just copy the existing CSV
                import shutil
                shutil.copy2(self.csv_path, output_path)
            
            elif format.lower() == 'json':
                # Copy the detailed JSON
                import shutil
                shutil.copy2(self.json_path, output_path)
            
            elif format.lower() == 'xlsx':
                # Convert to Excel
                df = pd.read_csv(self.csv_path)
                df.to_excel(output_path, index=False)
            
            logger.info(f"Data exported to: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return ""
    
    def generate_report(self) -> str:
        """Generate a comprehensive application report"""
        try:
            stats = self.get_application_stats()
            recent_apps = self.get_recent_applications(7)
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            report_path = config.OUTPUT_DIR / f"application_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(report_path, 'w') as f:
                f.write("AutoApply Agent - Application Report\\n")
                f.write("=" * 50 + "\\n")
                f.write(f"Generated: {timestamp}\\n\\n")
                
                # Overall statistics
                f.write("OVERALL STATISTICS\\n")
                f.write("-" * 20 + "\\n")
                f.write(f"Total Applications: {stats.get('total_applications', 0)}\\n")
                f.write(f"Applications Today: {stats.get('applications_today', 0)}\\n")
                f.write(f"Companies Applied: {stats.get('companies_applied', 0)}\\n")
                f.write(f"Success Rate: {stats.get('success_rate', 0):.1f}%\\n\\n")
                
                # Status breakdown
                f.write("STATUS BREAKDOWN\\n")
                f.write("-" * 15 + "\\n")
                for status, count in stats.get('status_breakdown', {}).items():
                    f.write(f"{status.title()}: {count}\\n")
                f.write("\\n")
                
                # Platform breakdown
                f.write("PLATFORM BREAKDOWN\\n")
                f.write("-" * 18 + "\\n")
                for platform, count in stats.get('platform_breakdown', {}).items():
                    f.write(f"{platform}: {count}\\n")
                f.write("\\n")
                
                # Recent applications
                f.write("RECENT APPLICATIONS (Last 7 days)\\n")
                f.write("-" * 35 + "\\n")
                for app in recent_apps[-10:]:  # Show last 10
                    f.write(f"• {app.get('job_title', 'Unknown')} at {app.get('company', 'Unknown')}\\n")
                    f.write(f"  Status: {app.get('status', 'Unknown')} | Date: {app.get('date', 'Unknown')}\\n")
                    f.write(f"  Platform: {app.get('platform', 'Unknown')}\\n\\n")
            
            logger.info(f"Report generated: {report_path}")
            return str(report_path)
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return ""
    
    def cleanup_old_data(self, days: int = 90):
        """Clean up old application data (optional)"""
        try:
            # This is optional - for now, we'll just log the action
            cutoff_date = datetime.now() - pd.Timedelta(days=days)
            logger.info(f"Would clean up applications older than {cutoff_date.strftime('%Y-%m-%d')}")
            
            # In a real implementation, you might want to archive old data
            # rather than delete it
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")

# Utility functions for batch operations
def track_batch_applications(jobs_with_results: List[Dict], tracker: ApplicationTracker = None) -> List[str]:
    """Track multiple applications in batch"""
    if not tracker:
        tracker = ApplicationTracker()
    
    app_ids = []
    for job_result in jobs_with_results:
        try:
            app_id = tracker.add_application(
                job_data=job_result['job_data'],
                cv_path=job_result['cv_path'],
                application_result=job_result['application_result'],
                profile_data=job_result.get('profile_data')
            )
            app_ids.append(app_id)
        except Exception as e:
            logger.error(f"Error tracking application: {e}")
            continue
    
    return app_ids

# Example usage and testing
def test_tracker():
    """Test tracker functionality"""
    tracker = ApplicationTracker()
    
    # Sample data
    job_data = {
        'title': 'Senior Python Developer',
        'company': 'TechCorp',
        'location': 'Bangalore, India',
        'application_url': 'https://techcorp.com/apply',
        'source_channel': '@jobs_channel'
    }
    
    application_result = {
        'status': 'submitted',
        'platform': 'Company Website'
    }
    
    # Add application
    app_id = tracker.add_application(job_data, '/path/to/cv.pdf', application_result)
    print(f"Added application: {app_id}")
    
    # Get stats
    stats = tracker.get_application_stats()
    print(f"Stats: {stats}")
    
    # Update status
    tracker.update_application_status(app_id, 'interview', 'Got interview call!')
    
    # Generate report
    report_path = tracker.generate_report()
    print(f"Report generated: {report_path}")

if __name__ == "__main__":
    test_tracker()
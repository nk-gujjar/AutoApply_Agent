# AutoApply Agent

A Python-based autonomous job application agent that scrapes Telegram channels for job postings, filters by criteria, generates tailored CVs, and automates the application process.

## Features

- 🔍 **Telegram Job Scraping**: Monitors Telegram channels for job postings using Telethon
- 🤖 **AI-Powered Processing**: Uses Google Gemini to parse unstructured job descriptions
- 📄 **Dynamic CV Generation**: Creates tailored CVs for each job application
- 🚀 **Web Automation**: Automates applications on job portals (Workday, Naukri, etc.) using Playwright
- 📧 **Email Applications**: Sends applications via email when required
- 👤 **Human-in-the-Loop**: Prompts for missing profile information when needed
- 📊 **Application Tracking**: Maintains detailed records of all applications

## Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <repository-url>
   cd AutoApply_Agent
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   - Copy `.env.example` to `.env` and fill in your API keys:
     - Telegram API ID and Hash (get from https://my.telegram.org)
     - Google Gemini API Key (get from https://ai.google.dev)
     - Email credentials (optional, for email applications)

3. **Update Personal Profile**:
   - Edit `personal.txt` with your information
   - Or run `python main.py --mode update-profile` for interactive setup

4. **Run the Agent**:
   ```bash
   # Batch mode - search and apply to jobs from last 7 days
   python main.py --mode batch --days 7
   
   # Monitor mode - continuous monitoring for new jobs
   python main.py --mode monitor
   
   # View statistics
   python main.py --mode stats
   ```

## Project Structure

```
AutoApply_Agent/
├── main.py              # Main orchestrator
├── config.py            # Configuration management
├── scraper.py           # Telegram scraping
├── processor.py         # AI job processing
├── cv_engine.py         # CV generation
├── automator.py         # Web/email automation
├── human_loop.py        # User interaction handling
├── tracker.py           # Application tracking
├── personal.txt         # Your profile information
├── .env                 # Environment variables
├── requirements.txt     # Python dependencies
├── data/                # Generated data files
├── logs/                # Application logs
├── output/              # Generated CVs and reports
└── templates/           # CV templates
```

## Core Modules

### 1. Scraper (`scraper.py`)
- Monitors Telegram channels using Telethon
- Filters messages based on job keywords, experience, and CTC criteria
- Supports both batch scraping and real-time monitoring

### 2. Processor (`processor.py`)
- Uses Google Gemini to parse unstructured job descriptions
- Converts text into structured JSON format
- Validates and filters jobs based on user criteria

### 3. CV Engine (`cv_engine.py`)
- Generates tailored CVs using AI based on job requirements
- Converts CV content to PDF format
- Maintains CV generation history and metadata

### 4. Automator (`automator.py`)
- Handles web-based applications using Playwright
- Supports major job portals (Workday, Naukri, LinkedIn)
- Sends email applications when required
- Includes anti-detection measures for web scraping

### 5. Human Loop (`human_loop.py`)
- Manages user profile validation
- Prompts for missing information when needed
- Uses Pydantic models for data validation

### 6. Tracker (`tracker.py`)
- Maintains application history in CSV, JSON, and TXT formats
- Provides statistics and reporting
- Tracks application status and responses

## Configuration

### Environment Variables (.env)
```bash
# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
BOT_TOKEN=your_bot_token  # Optional

# AI API
GEMINI_API_KEY=your_gemini_key

# Email (Optional)
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# Job Criteria
TARGET_ROLES=SDE,Software Engineer,Backend Developer
MIN_EXPERIENCE=0
MAX_EXPERIENCE=5
MIN_CTC=10
TARGET_CHANNELS=@jobs_channel1,@jobs_channel2

# Application Settings
MAX_APPLICATIONS_PER_DAY=10
DELAY_BETWEEN_APPLICATIONS=300
AUTO_APPLY=false  # Set to true for fully automated applications
```

### Personal Profile (personal.txt)
Fill in your personal information in the provided template. The system will prompt you for any missing required fields.

## Usage Examples

### Batch Job Search and Application
```bash
# Search for jobs from last 7 days and apply
python main.py --mode batch --days 7

# Search from last 3 days
python main.py --mode batch --days 3
```

### Real-time Monitoring
```bash
# Start monitoring for new job posts
python main.py --mode monitor
```

### Statistics and Reports
```bash
# View application statistics
python main.py --mode stats

# Generate detailed report
python main.py --mode report

# Update your profile interactively
python main.py --mode update-profile
```

### Programmatic Usage
```python
from main import AutoApplyAgent

# Create and initialize agent
agent = AutoApplyAgent()
await agent.initialize()

# Run full pipeline
results = await agent.run_full_pipeline(days_back=7)
print(f"Applied to {results['successful_applications']} jobs")
```

## Supported Platforms

- **Web Portals**: Workday, Naukri.com, LinkedIn (Easy Apply), Generic job boards
- **Email Applications**: SMTP-based email sending
- **Telegram Channels**: Any public Telegram channel with job postings

## Safety Features

- **Daily Application Limits**: Prevents spam applications
- **Human Review**: Option to review applications before submission
- **Profile Validation**: Ensures complete information before applying
- **Error Handling**: Comprehensive logging and error recovery
- **Anti-Detection**: Stealth browsing techniques for web automation

## Output Files

- `data/tracker.csv` - Application tracking spreadsheet
- `data/applications.json` - Detailed application data
- `data/history.txt` - Human-readable application history
- `output/cv_*.pdf` - Generated CVs
- `logs/autoapply.log` - Application logs

## Troubleshooting

### Common Issues

1. **Telegram Connection Fails**:
   - Verify API ID and Hash from https://my.telegram.org
   - Check internet connection
   - Ensure phone number is verified

2. **Gemini API Errors**:
   - Verify API key from https://ai.google.dev
   - Check API quota and billing
   - Ensure proper internet access

3. **Web Automation Fails**:
   - Try running with `--headless false` to see browser
   - Check if job portal has updated their interface
   - Verify network connectivity

4. **Email Sending Fails**:
   - Use app-specific passwords for Gmail
   - Check SMTP settings
   - Verify email credentials

### Debug Mode
```bash
# Run with verbose logging
python main.py --mode batch --days 1 --verbose

# Run browser in visible mode (for debugging web automation)
python main.py --mode batch --headless false
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Disclaimer

This tool is for educational and personal use only. Always:
- Respect website terms of service
- Follow job application etiquette
- Review applications before submission
- Use responsibly and ethically

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs in `logs/autoapply.log`
3. Open an issue on GitHub

---

**Happy Job Hunting! 🚀**
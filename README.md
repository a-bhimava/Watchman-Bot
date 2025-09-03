# PM Watchman - Automated Job Search System

A reliable local application that discovers 40-50 Product Manager job postings daily, scores them against your personalized PM profile, and delivers 10 relevant jobs every 6 hours via Telegram.

## Quick Start

1. **Setup Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure System**
   - Copy `examples/sample_pm_profile.json` to `config/pm_profile.json`
   - Set up Telegram bot credentials in `.env`
   - Customize job sources in `config/job_sources.json`

3. **Run System**
   ```bash
   python main.py
   ```

## Project Structure

```
├── src/                    # Source code
│   ├── core/              # Core system modules
│   ├── integrations/      # External service integrations
│   └── utils/             # Utility functions
├── config/                # Configuration files
├── data/                  # Data storage
│   ├── cache/            # Temporary job data
│   ├── sent/             # Sent jobs tracking
│   └── logs/             # System logs
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── docs/                  # Documentation
└── examples/              # Configuration examples
```

## Features

- **Multi-source Job Discovery**: LinkedIn + RSS feeds
- **Intelligent Scoring**: 0-100 relevance score based on your PM profile
- **Batch Delivery**: 4 batches of 10 jobs daily via Telegram
- **Duplicate Prevention**: 30-day tracking to avoid repeats
- **Local Execution**: Runs on your machine with cron automation

## Documentation

See `docs/` for detailed setup and usage instructions.
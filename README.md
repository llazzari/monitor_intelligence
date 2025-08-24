# Monitor Intelligence

This repository contains solutions for checkout behavior analysis and a real-time transactions alert system. The project demonstrates data analysis, anomaly detection, and monitoring using Python, SQL, and modern web technologies.

## Project Structure
- `checkout_analysis/` — Jupyter notebook and scripts for checkout data analysis
- `transactions_alert_system/` — Source code for the anomaly detection API, dashboard, and notification system
- `requirements.txt` — Python dependencies
- `results.pdf` — Methodology and results documentation

## Setup Instructions
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd MonitorIntelligence
   ```
2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **(Optional) Set up environment variables for email notifications:**
   - Create a `.env` file or export variables in your terminal:
     ```bash
     export SMTP_USER=your-email@gmail.com
     export SMTP_PASS=your-app-password
     export ALERT_RECIPIENTS=recipient1@example.com,recipient2@example.com
     ```

## Running the Transactions Alert System
Start the FastAPI server from the project root:
```bash
uvicorn transactions_alert_system.src.app:app --reload
```

Visit [http://127.0.0.1:8000/docs/](http://127.0.0.1:8000/docs/) for interactive API documentation.

## License
This project is for demonstration and evaluation purposes.

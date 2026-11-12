# PULSE Prototype

Patient Updates, Logs, Scheduling & Evaluation.

## Run locally
1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Run `pip install -r requirements.txt`.
4. Run `streamlit run app.py`.

## Deploy
Push `app.py`` and `requirements.txt` to a GitHub repository, then deploy the repository through Streamlit Community Cloud.

## Important demo limitations
- The 38.0°C fever threshold is an assumption, not specified in the assessment.
- The role selector is a demonstration switch, not secure authentication.
- SQLite persistence on hosted environments may not be durable. A production system needs managed persistent storage, authentication, audit logging, privacy/security controls, backups, and clinical validation.
- This prototype is not for clinical use.

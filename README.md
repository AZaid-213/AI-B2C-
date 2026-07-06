# AI B2C

This project contains a full-stack B2C application with:

- a FastAPI backend for contact management, campaign workflows, and AI-assisted responses
- a Vite + React frontend for the user interface
- environment-based configuration for GreenAPI, Redis, and Groq

## Project Structure

- backend/ - FastAPI server, routes, services, and background tasks
- frontend/ - Vite React application

## Setup

1. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

3. Create a backend/.env file with the required environment variables.

4. Start the backend and frontend services.

## Notes

- Sensitive values such as API keys and credentials should be stored in environment variables and not committed to source control.
- The repository includes a .gitignore file to avoid committing local environment files.

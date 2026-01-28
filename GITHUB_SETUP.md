# GitHub Setup Checklist

## Before Pushing

1. **Verify .gitignore is working:**
   ```bash
   git status
   ```
   Make sure these are NOT tracked:
   - credentials.json
   - .env
   - data/*.json
   - data/*.db
   - data/cache/
   - venv/
   - __pycache__/

2. **Review sensitive files:**
   - Ensure no API keys or passwords are in committed files
   - Check that credentials.json is in .gitignore

3. **Initial commit (if not already done):**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: MediTrack EMS & Police Aircraft Tracking System"
   ```

4. **Create GitHub repository:**
   - Go to https://github.com/new
   - Create a new repository (don't initialize with README)
   - Copy the repository URL

5. **Push to GitHub:**
   ```bash
   git remote add origin https://github.com/yourusername/MediTrack-git.git
   git branch -M main
   git push -u origin main
   ```

## Files Included

✅ Source code (src/)
✅ Configuration files (config.py, requirements.txt)
✅ Documentation (README.md, LICENSE)
✅ Example environment file (.env.example)
✅ FAA database structure (ReleasableAircraft/ - if you want to include it)

## Files Excluded (via .gitignore)

❌ Credentials (credentials.json, .env)
❌ Generated databases (data/*.json, data/*.db)
❌ Cache files (data/cache/)
❌ Virtual environment (venv/)
❌ Python cache (__pycache__/)
❌ Test files (test_*.py)

## Notes

- Users will need to download FAA database files separately (they're large)
- Users will need to create their own credentials.json with OpenSky API credentials
- The .env.example file shows what environment variables are available

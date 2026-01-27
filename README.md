# Flask Text Submission App

A simple Flask application for submitting and viewing text entries. Ready to deploy on Render.

## Features

- **Beautiful UI**: Clean, modern interface with gradient design
- **Text Submission**: Users can enter their name and text
- **Real-time Display**: View all submissions instantly
- **RESTful API**: Full API endpoints for programmatic access
- **Render-Ready**: Configured for easy deployment

## Project Structure

```
Jenkins_AWS_Flask/
├── app.py                 # Main Flask application
├── templates/
│   └── index.html        # UI template
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore file
└── README.md             # This file
```

## API Endpoints

### Submit Text
```
POST /api/submit
Content-Type: application/json

{
  "name": "John Doe",
  "text": "Your text here"
}
```

### Get All Submissions
```
GET /api/submissions
```

### Get Specific Submission
```
GET /api/submissions/<id>
```

### Health Check
```
GET /api/health
```

## Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Jenkins_AWS_Flask
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Mac/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open browser**
   ```
   http://localhost:5000
   ```

## Deploy to Render

### Step 1: Push to GitHub

1. Initialize git (if not already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Create a new repository on GitHub

3. Push your code:
   ```bash
   git remote add origin https://github.com/yourusername/your-repo-name.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy on Render

1. **Create Render Account**
   - Go to [render.com](https://render.com)
   - Sign up or log in
   - Connect your GitHub account

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Select your repository
   - Configure the service:

3. **Configuration Settings**
   ```
   Name: flask-text-app (or your preferred name)
   Region: Select closest to you
   Branch: main
   Root Directory: (leave blank)
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   Instance Type: Free
   ```

4. **Advanced Settings (Optional)**
   - Add environment variables if needed
   - Set Python version: `3.11.0` (or your version)

5. **Deploy**
   - Click "Create Web Service"
   - Wait for deployment (3-5 minutes)
   - Your app will be live at: `https://your-app-name.onrender.com`

### Important Notes for Render

- ✅ `gunicorn` is included in `requirements.txt`
- ✅ Build command: `pip install -r requirements.txt`
- ✅ Start command: `gunicorn app:app`
- ✅ App binds to `0.0.0.0` and uses `PORT` environment variable
- ⚠️ Free tier apps sleep after 15 minutes of inactivity
- ⚠️ First request after sleep may take 30-60 seconds

## Troubleshooting

### Deployment Issues

1. **App won't start**
   - Check logs in Render dashboard
   - Verify `requirements.txt` has all dependencies
   - Ensure `gunicorn` is installed

2. **404 Errors**
   - Verify start command is `gunicorn app:app`
   - Check app.py exists in root directory

3. **Slow first load**
   - Normal for free tier (cold start)
   - Consider upgrading for production use

## Future Enhancements

- Add database (PostgreSQL) for persistent storage
- Integrate LLM API for text analysis
- Add user authentication
- File upload support
- Export submissions as CSV/JSON

## Tech Stack

- **Backend**: Flask 3.0
- **Server**: Gunicorn 21.2
- **Frontend**: Vanilla JavaScript + HTML5 + CSS3
- **Deployment**: Render

## License

MIT License - Feel free to use and modify!

---

**Ready to deploy?** Follow the steps above and your app will be live in minutes! 🚀

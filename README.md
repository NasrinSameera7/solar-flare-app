# Solar Flare & Space Weather Prediction Pipeline

A full-stack web application for real-time solar flare monitoring and ML-based space weather prediction.

🌐 **Live Demo**: [your-vercel-url.vercel.app](https://your-app.vercel.app)  
🔌 **API Docs**: [your-render-url.onrender.com/docs](https://solar-flare-api.onrender.com/docs)

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | HTML + CSS + JavaScript (Chart.js) |
| Backend | Python FastAPI |
| ML Model | scikit-learn Random Forest |
| Data | NASA DONKI API + NOAA SWPC |
| Frontend Deploy | Vercel (free) |
| Backend Deploy | Render (free) |

---

## Project Structure

```
solar-flare-app/
├── backend/          ← Python FastAPI backend
│   ├── main.py
│   ├── routers/      ← API endpoints
│   ├── services/     ← NASA/NOAA clients + ML engine
│   ├── requirements.txt
│   └── render.yaml
└── frontend/         ← Static HTML/CSS/JS dashboard
    ├── index.html
    ├── style.css
    ├── app.js
    └── vercel.json
```

---

## Local Development

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API available at: http://localhost:8000  
Swagger docs: http://localhost:8000/docs

### 2. Frontend

Open `frontend/index.html` in your browser. Make sure `API_BASE` in `app.js` is set to `http://localhost:8000`.

---

## Deployment to the Public Internet

### Step 1: Create a GitHub Repository

1. Go to [github.com](https://github.com) and create a **new public repository** named `solar-flare-app`
2. Push this entire folder:

```bash
cd solar-flare-app
git init
git add .
git commit -m "Initial commit: Solar Flare Prediction Pipeline"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/solar-flare-app.git
git push -u origin main
```

---

### Step 2: Deploy Backend to Render (Free)

1. Go to **[render.com](https://render.com)** → Sign up for free (use GitHub login)
2. Click **New +** → **Web Service**
3. Connect your GitHub account and select the `solar-flare-app` repository
4. Configure:
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - `NASA_API_KEY` = `DEMO_KEY` (or your real key from api.nasa.gov)
6. Click **Create Web Service** → Wait 3-5 minutes for deployment
7. Your backend URL will be: `https://solar-flare-api.onrender.com` (or similar)

> **Note**: Free Render services sleep after 15 minutes of inactivity. The first request after sleep takes ~30 seconds. This is fine for a demo.

---

### Step 3: Update Frontend API URL

Edit `frontend/app.js` — replace this line:

```js
: "https://solar-flare-api.onrender.com"; // ← Update with your Render URL
```

With your actual Render URL.

Also update `frontend/vercel.json`:
```json
"destination": "https://YOUR-RENDER-URL.onrender.com/api/$1"
```

---

### Step 4: Deploy Frontend to Vercel (Free)

1. Go to **[vercel.com](https://vercel.com)** → Sign up for free (use GitHub login)
2. Click **Add New Project** → Import your GitHub repository
3. Configure:
   - **Framework Preset**: `Other`
   - **Root Directory**: `frontend`
4. Click **Deploy** → Wait 1-2 minutes
5. Your public URL will be: `https://solar-flare-app.vercel.app`

---

### Step 5: Update CORS in Backend (Optional)

If you want to restrict CORS to only your Vercel domain, edit `backend/main.py`:

```python
allow_origins=["https://your-app.vercel.app"],
```

Then push the change — Render will auto-redeploy.

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /api/flares?days=30` | Solar flare events |
| `GET /api/cme?days=30` | CME events |
| `GET /api/geomagnetic` | Kp index + storm data |
| `GET /api/predict` | ML flare prediction |
| `GET /api/predict/history` | Prediction history |
| `GET /api/solar-wind` | Solar wind Bz data |
| `GET /api/alerts` | Active NOAA alerts |
| `GET /api/forecast` | 3-day NOAA forecast |
| `GET /docs` | Swagger UI |

---

## Data Sources

- **NASA DONKI API** — Solar flares, CMEs, geomagnetic storms, SEP events
- **NOAA SWPC** — Real-time X-ray flux, Kp index, space weather alerts
- API key: `DEMO_KEY` (free, no registration required — 30 req/hr)

---

## ML Model

- **Algorithm**: Random Forest Classifier (scikit-learn)
- **Target**: Predict next-24h solar flare class (Quiet / C / M / X)
- **Features**: Recent flare history, CME count, Kp index, active region data
- **Training**: Automatic on startup using last 90 days of NASA DONKI data
- **Re-training**: Every 6 hours via APScheduler

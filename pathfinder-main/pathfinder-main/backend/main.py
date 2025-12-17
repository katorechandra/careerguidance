from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from groq import Groq
from dotenv import load_dotenv
import os
import logging
import json
from starlette.concurrency import run_in_threadpool

# ----- Load environment -----
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
if not API_KEY:
    logger.warning("GROQ_API_KEY not set")

# ----- Initialize client -----
client = Groq(api_key=API_KEY)

# ----- FastAPI setup -----
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Path Configurations -----
# Assuming backend is at main_root/backend/main.py
# Frontend is at main_root/frontend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

# Mount Static Files
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
else:
    logger.warning("Static directory not found at: %s", STATIC_DIR)

# Initialize Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ----- Pydantic model -----
class QuizSubmission(BaseModel):
    answers: dict
    category: Optional[str] = None

# ----- Helper: clean possible markdown/code fences -----
def _extract_json(text: str):
    # strip code fences if present
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        # remove triple backticks and optional language
        parts = text.split('```')
        # join middle parts
        if len(parts) >= 3:
            text = '```'.join(parts[1:-1]).strip()
        else:
            text = parts[1].strip()
    # try to find first { ... } block
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text

# ----- Function to produce deterministic recommendations for After-10 -----
def generate_after10_recommendations(answers: dict):
    # Normalize keys and values
    q1 = (answers.get('q1') or answers.get('q1', '')).strip() if isinstance(answers, dict) else ''
    q2 = (answers.get('q2') or answers.get('q2', '')).strip() if isinstance(answers, dict) else ''
    q3 = (answers.get('q3') or answers.get('q3', '')).strip() if isinstance(answers, dict) else ''
    q4 = (answers.get('q4') or answers.get('q4', '')).strip() if isinstance(answers, dict) else ''
    q5 = (answers.get('q5') or answers.get('q5', '')).strip() if isinstance(answers, dict) else ''

    scores = {"Arts": 0, "Commerce": 0, "Diploma": 0, "Science": 0}
    reasons = {k: [] for k in scores}

    # Q1: subject preference
    if q1.lower().startswith('mathemat') or 'mathemat' in q1.lower():
        scores['Commerce'] += 2
        scores['Science'] += 1
        reasons['Commerce'].append('Strong preference for Mathematics')
    elif q1.lower().startswith('science') or 'science' in q1.lower():
        scores['Science'] += 3
        reasons['Science'].append('Enjoys Science subjects and experiments')
    elif 'languag' in q1.lower() or 'languages' in q1.lower():
        scores['Arts'] += 3
        reasons['Arts'].append('Strong interest in languages and humanities')
    elif 'social' in q1.lower():
        scores['Arts'] += 2
        scores['Commerce'] += 1
        reasons['Arts'].append('Interest in social studies and society topics')

    # Q2: study preference
    if 'practical' in q2.lower() or 'experiment' in q2.lower():
        scores['Diploma'] += 2
        scores['Science'] += 1
        reasons['Diploma'].append('Prefers hands-on/practical learning')
    elif 'theory' in q2.lower() or 'reading' in q2.lower():
        scores['Commerce'] += 2
        scores['Arts'] += 1
        reasons['Commerce'].append('Prefers theoretical and reading-based study')
    elif 'both' in q2.lower():
        for k in scores: scores[k] += 1
        reasons['Arts'].append('Enjoys both practical and theoretical approaches')
    else:
        # Not sure
        scores['Diploma'] += 1
        reasons['Diploma'].append('Undecided; practical paths can provide early clarity')

    # Q3: plan after 10th
    if 'science' in q3.lower():
        scores['Science'] += 3
        reasons['Science'].append('Plans to pursue Science (11-12)')
    elif 'commerce' in q3.lower():
        scores['Commerce'] += 3
        reasons['Commerce'].append('Plans to pursue Commerce (11-12)')
    elif 'arts' in q3.lower():
        scores['Arts'] += 3
        reasons['Arts'].append('Plans to pursue Arts (11-12)')
    elif 'diploma' in q3.lower() or 'iti' in q3.lower():
        scores['Diploma'] += 3
        reasons['Diploma'].append('Plans for Diploma/ITI (skill-based path)')

    # Q4: main goal
    if 'higher' in q4.lower():
        scores['Science'] += 1
        scores['Commerce'] += 1
        scores['Arts'] += 1
        reasons['Science'].append('Goal: higher education')
    elif 'skill' in q4.lower():
        scores['Diploma'] += 2
        reasons['Diploma'].append('Goal: skill-based learning')
    elif 'early' in q4.lower():
        scores['Diploma'] += 2
        reasons['Diploma'].append('Goal: early job')
    else:
        # Still confused
        for k in scores: scores[k] += 1
        reasons['Arts'].append('Uncertain goals; consider exploratory options')

    # Q5: confidence
    if 'very' in q5.lower():
        for k in scores: scores[k] += 1
    elif 'somewhat' in q5.lower():
        pass
    elif 'confused' in q5.lower() or 'need' in q5.lower():
        scores['Diploma'] += 1
        reasons['Diploma'].append('May benefit from hands-on exploration')

    # Build result entries with descriptions and next steps
    career_templates = {
        'Arts': {
            'description': 'Humanities and creative fields (languages, social sciences, arts).',
            'next_steps': 'Consider taking Arts in 11-12, join debate/writing clubs, explore short courses in media, design, or humanities.'
        },
        'Commerce': {
            'description': 'Business, accounting, and finance-related paths.',
            'next_steps': 'Consider Commerce in 11-12, learn basic accounting and Excel, look into business studies and economics.'
        },
        'Diploma': {
            'description': 'Skill-focused diplomas, ITI, and vocational training leading to early work.',
            'next_steps': 'Research local diploma or ITI programs, apprenticeships, and skill courses; try short vocational workshops.'
        },
        'Science': {
            'description': 'Science stream leading to engineering, medicine, pure sciences and technical roles.',
            'next_steps': 'Prepare for 11-12 science stream, engage in lab work or science projects, consider coaching for competitive exams if aiming for professional programs.'
        }
    }

    # Compose careers list in order of score
    items = []
    for key, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
        reason_text = '; '.join(reasons.get(key, [])) or 'Matches your responses.'
        items.append({
            'title': key,
            'description': career_templates[key]['description'],
            'why_fit': reason_text,
            'next_steps': career_templates[key]['next_steps'],
            'score': score
        })

    # Generate a personalized profile summary based on collected reasons
    # Identify dominant interest (highest score)
    top_career = max(scores, key=scores.get)
    
    # Contextualize with specific answers
    # Q2: Learning style (Practical/Theory)
    style_text = "hands-on learning"
    if 'theory' in q2.lower() or 'reading' in q2.lower():
        style_text = "theoretical study"
    elif 'both' in q2.lower():
        style_text = "a balance of practice and theory"
        
    # Q4: Goal (Higher ed/Job/Skill)
    goal_text = "building a strong academic foundation"
    if 'skill' in q4.lower():
        goal_text = "acquiring practical job-ready skills"
    elif 'early' in q4.lower():
        goal_text = "starting your career early"
        
    summary = f"Your responses suggest a strong affinity for {top_career}-related fields. You seem to prefer {style_text}, which aligns well with your goal of {goal_text}. This combination indicates you would thrive in environments that offer {career_templates[top_career]['description'].lower()}"

    details = 'Use the next steps to explore the recommended paths; consider talking to a counselor for personalized guidance.'

    return {'summary': summary, 'careers': items, 'details': details}


# ----- Function to produce deterministic recommendations for After-12 -----
def generate_after12_recommendations(answers: dict):
    # Normalize keys/values
    # questions in frontend: q1_12, q3_12, q4_12, q5_12, q6_12 (q2 skipped in naming)
    q1 = (answers.get('q1_12') or '').strip()  # Stream
    q2 = (answers.get('q3_12') or '').strip()  # Next Step
    q3 = (answers.get('q4_12') or '').strip()  # Interest
    q4 = (answers.get('q5_12') or '').strip()  # Exams
    q5 = (answers.get('q6_12') or '').strip()  # Long term

    scores = {
        "Engineering/Medical": 0,
        "Degree (BSc/BCom/BA)": 0,
        "Professional (CA/CS)": 0,
        "Skill-based course": 0,
        "Government/Public Service": 0
    }
    reasons = {k: [] for k in scores}

    # Q1: Stream from 12th
    if 'Science' in q1:
        scores['Engineering/Medical'] += 2
        scores['Degree (BSc/BCom/BA)'] += 1
        reasons['Engineering/Medical'].append('Background in Science')
    elif 'Commerce' in q1:
        scores['Professional (CA/CS)'] += 2
        scores['Degree (BSc/BCom/BA)'] += 1
        reasons['Professional (CA/CS)'].append('Background in Commerce')
    elif 'Arts' in q1:
        scores['Degree (BSc/BCom/BA)'] += 2
        scores['Government/Public Service'] += 1
        reasons['Degree (BSc/BCom/BA)'].append('Background in Arts')
    elif 'Vocational' in q1:
        scores['Skill-based course'] += 3
        reasons['Skill-based course'].append('Background in Vocational studies')

    # Q2: Plan Next (direct preference)
    if 'Engineering' in q2 or 'Medical' in q2:
        scores['Engineering/Medical'] += 3
        reasons['Engineering/Medical'].append('Direct interest in professional technical degrees')
    elif 'Degree' in q2:
        scores['Degree (BSc/BCom/BA)'] += 3
        reasons['Degree (BSc/BCom/BA)'].append('Preference for standard undergraduate degree')
    elif 'Professional' in q2:
        scores['Professional (CA/CS)'] += 3
        reasons['Professional (CA/CS)'].append('Interest in specialized professional path')
    elif 'Skill' in q2:
        scores['Skill-based course'] += 3
        reasons['Skill-based course'].append('Preference for skill-oriented training')

    # Q3: Work Interest
    if 'Technical' in q3:
        scores['Engineering/Medical'] += 1
        scores['Skill-based course'] += 1
    elif 'Management' in q3:
        scores['Professional (CA/CS)'] += 1
        scores['Degree (BSc/BCom/BA)'] += 1
    elif 'Creative' in q3:
        scores['Degree (BSc/BCom/BA)'] += 1
        scores['Skill-based course'] += 1
    elif 'Social' in q3:
        scores['Government/Public Service'] += 2
        scores['Degree (BSc/BCom/BA)'] += 1
        reasons['Government/Public Service'].append('Interest in social service')

    # Q4: Competitive Exams
    if 'Very comfortable' in q4:
        scores['Engineering/Medical'] += 1
        scores['Professional (CA/CS)'] += 1
        scores['Government/Public Service'] += 1
    elif 'Not interested' in q4:
        scores['Degree (BSc/BCom/BA)'] += 1
        scores['Skill-based course'] += 1
        reasons['Skill-based course'].append('Prefers avoiding competitive entrance exams')

    # Q5: Long Term
    if 'High-paying' in q5:
        scores['Engineering/Medical'] += 1
        scores['Professional (CA/CS)'] += 1
    elif 'Government' in q5:
        scores['Government/Public Service'] += 3
        reasons['Government/Public Service'].append('Goal is government service')
    elif 'Higher studies' in q5:
        scores['Degree (BSc/BCom/BA)'] += 2
        reasons['Degree (BSc/BCom/BA)'].append('Long-term academic goals')
    elif 'Entrepreneurship' in q5:
        scores['Professional (CA/CS)'] += 1
        scores['Skill-based course'] += 1

    # Templates
    career_templates = {
        'Engineering/Medical': {
            'description': 'Rigorous technical or medical degrees (B.Tech, MBBS) leading to specialized careers.',
            'next_steps': 'Prepare for JEE, NEET, or state level entrance exams; research top colleges.'
        },
        'Degree (BSc/BCom/BA)': {
            'description': 'Academic undergraduate programs offering flexibility and foundation for masters.',
            'next_steps': 'Choose a major you enjoy; consider internships and extra-curriculars to build profile.'
        },
        'Professional (CA/CS)': {
            'description': 'Specialized professional certifications in finance, law, or management.',
            'next_steps': 'Register for foundation courses (e.g. CA Foundation); join coaching if needed.'
        },
        'Skill-based course': {
            'description': 'Short-term or vocational courses focused on job-readiness (Design, Coding, etc).',
            'next_steps': 'Build a portfolio; look for certifications from recognized platforms or institutes.'
        },
        'Government/Public Service': {
            'description': 'Careers in civil services, banking, or bady public sector roles.',
            'next_steps': 'Start general awareness reading; check eligibility for exams like SSC, UPSC, or Banking.'
        }
    }

    # Rank and Build
    items = []
    for key, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
        reason_text = '; '.join(reasons.get(key, [])) or 'Fits your profile.'
        items.append({
            'title': key,
            'description': career_templates[key]['description'],
            'why_fit': reason_text,
            'next_steps': career_templates[key]['next_steps'],
            'score': score
        })

    # Summary
    # Summary construction
    # Identify top career
    top_career = max(scores, key=scores.get)
    
    # Pointers
    stream_val = q1 if q1 else "your current stream"
    interest_val = q3 if q3 else "particular"
    goal_val = q5 if q5 else "future stability"
    
    # Template
    summary = f"With a background in {stream_val}, your interest in {interest_val} roles creates a strong profile for {top_career}. You appear to be driven by {goal_val}, making this path a strategic choice for your long-term success."

    details = "Review the top matches below. Each path has specific entrance requirements, so plan your preparation accordingly."

    return {'summary': summary, 'careers': items, 'details': details}


# ----- Function to call Groq (synchronous; run in threadpool) -----
def analyze_answers(answers, category=None):
    # If category is after10, use deterministic generator
    if category == 'after10':
        try:
            return generate_after10_recommendations(answers)
        except Exception as e:
            logger.exception('Error generating after10 recommendations: %s', e)
            return {
                'summary': 'Error generating recommendations.',
                'careers': [],
                'details': str(e)
            }
    # If category is after12, use deterministic generator
    if category == 'after12':
        try:
            return generate_after12_recommendations(answers)
        except Exception as e:
            logger.exception('Error generating after12 recommendations: %s', e)
            return {
                'summary': 'Error generating recommendations.',
                'careers': [],
                'details': str(e)
            }
        prompt = f"""
Analyze the following quiz answers and suggest the top 5 career paths: {answers}
Return a JSON object exactly in this format:
{{
  "summary": "A 2-3 sentence profile summary describing the user's strengths, interests, and personality based on their answers.",
  "careers": [
    {{"title": "...","description": "...","why_fit": "...","next_steps": "..."}},
    ... up to 5 items
  ],
  "details": "suggestions on how to get started"
}}

Important:
- Return valid JSON only (no surrounding markdown or explanations).
- Provide up to 5 career suggestions.
"""


    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_completion_tokens=2000,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
        )
        raw = completion.choices[0].message.content
        logger.debug("Raw model output: %s", raw)
        candidate = _extract_json(raw)
        try:
            return json.loads(candidate)
        except Exception:
            # fallback: try to load raw directly
            try:
                return json.loads(raw)
            except Exception as e:
                logger.exception("Failed to parse model JSON: %s", e)
                return {
                    "summary": "Generated suggestions (raw output could not be parsed).",
                    "careers": [],
                    "details": raw
                }
    except Exception as e:
        logger.exception("Groq API error: %s", e)
        return {
            "summary": "Error fetching career suggestions.",
            "careers": [],
            "details": str(e)
        }

# ----- Health endpoint -----
@app.get("/health")
async def health():
    return {"status": "ok"}

# ----- Frontend Routes (served via Jinja2) -----

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/verify-login")
async def verify_login():
    # Helper to satisfy frontend logic which expects a successful verification call
    return {"status": 'success'}

@app.get("/quiz")
async def quiz(request: Request):
    return templates.TemplateResponse("quiz.html", {"request": request})

@app.get("/result")
async def result(request: Request, career: Optional[str] = None):
    # 'career' might be passed as a query param or handled by client-side storage
    # We pass it to the context just in case
    return templates.TemplateResponse("result.html", {"request": request, "career": career or ""})


# ----- API endpoints -----

@app.post("/analyze")
async def analyze(submission: QuizSubmission):
    logger.info("Received submission; category=%s", submission.category)

    # If API key is missing, return a deterministic mock response for local dev
    if not API_KEY:
        logger.warning("GROQ_API_KEY not set — returning mock response for development")
        
        cat = submission.category
        # Fallback: identify category from answer keys if missing/unknown
        if not cat or cat not in ['after10', 'after12']:
            if 'q1_12' in submission.answers or 'q3_12' in submission.answers:
                cat = 'after12'
            else:
                cat = 'after10' # default to after10 if unsure
        
        return analyze_answers(submission.answers, cat)

    # Run the blocking model call in a threadpool with robust error handling
    try:
        result = await run_in_threadpool(analyze_answers, submission.answers, submission.category)
        return result
    except Exception as e:
        logger.exception("Unhandled error during analysis: %s", e)
        # Return structured error info rather than an opaque server error
        return JSONResponse(status_code=500, content={"error": "analysis_failed", "details": str(e)})

@app.post("/submit")
async def submit(submission: QuizSubmission):
    # Alias for /analyze to support frontend calls
    return await analyze(submission)

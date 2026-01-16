from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM Chat initialization
EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")


# ============= MODELS =============
class PhishingRequest(BaseModel):
    target_role: str
    difficulty: str
    industry: str

class PhishingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject: str
    body: str
    red_flags: List[str]
    analysis: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RansomwareRequest(BaseModel):
    attack_vector: str
    organization_type: str

class RansomwareResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attack_vector: str
    infection_flow: List[str]
    mitre_mapping: List[dict]
    prevention_tips: List[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AttackScenarioRequest(BaseModel):
    organization_type: str
    security_maturity: str

class AttackScenarioResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    timeline: List[dict]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TrainingQuestionRequest(BaseModel):
    scenario_type: str

class TrainingQuestionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question: str
    options: List[str]
    correct_answer: str
    explanation: str

class TrainingAnswerRequest(BaseModel):
    question_id: str
    user_answer: str

class TrainingAnswerResponse(BaseModel):
    correct: bool
    explanation: str
    score_gained: int

class DashboardStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_simulations: int
    phishing_sims: int
    ransomware_sims: int
    attack_scenarios: int
    training_score: int


# ============= HELPER FUNCTIONS =============
async def get_llm_response(prompt: str) -> str:
    try:
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"cyberrange-{uuid.uuid4()}",
            system_message="You are a cybersecurity expert helping create realistic training simulations. Always label outputs as 'SIMULATION ONLY' for educational purposes."
        ).with_model("gemini", "gemini-3-flash-preview")
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        return response
    except Exception as e:
        logging.error(f"LLM Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")


# ============= API ENDPOINTS =============
@api_router.get("/")
async def root():
    return {"message": "CyberRange AI API v1.0"}

@api_router.post("/phishing/generate", response_model=PhishingResponse)
async def generate_phishing(request: PhishingRequest):
    prompt = f"""Generate a realistic phishing email simulation for cybersecurity training.

Target Role: {request.target_role}
Difficulty: {request.difficulty}
Industry: {request.industry}

Provide:
1. Email subject line
2. Email body (realistic and detailed)
3. 3-5 red flags (phishing indicators)
4. Analysis explaining why it's phishing

Format as JSON with keys: subject, body, red_flags (array), analysis
[SIMULATION ONLY - Educational Purpose]"""

    llm_response = await get_llm_response(prompt)
    
    # Parse LLM response
    try:
        import json
        import re
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', llm_response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(llm_response)
    except:
        parsed = {
            "subject": "Urgent: Account Verification Required",
            "body": llm_response[:500],
            "red_flags": ["Urgency tactics", "Suspicious sender", "Generic greeting"],
            "analysis": "This is a simulated phishing attempt for training purposes."
        }
    
    phishing_data = PhishingResponse(
        subject=parsed.get('subject', 'Urgent Action Required'),
        body=parsed.get('body', llm_response),
        red_flags=parsed.get('red_flags', []),
        analysis=parsed.get('analysis', '')
    )
    
    # Store in database
    doc = phishing_data.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.phishing_simulations.insert_one(doc)
    
    return phishing_data

@api_router.post("/ransomware/generate", response_model=RansomwareResponse)
async def generate_ransomware(request: RansomwareRequest):
    prompt = f"""Generate a ransomware attack simulation for cybersecurity training.

Attack Vector: {request.attack_vector}
Organization Type: {request.organization_type}

Provide:
1. Step-by-step infection flow (5-7 steps)
2. MITRE ATT&CK mapping (3-5 techniques with IDs like T1566)
3. Prevention tips (3-5 actionable items)

Format as JSON with keys: infection_flow (array), mitre_mapping (array of objects with 'id' and 'name'), prevention_tips (array)
[SIMULATION ONLY - No Real Malware]"""

    llm_response = await get_llm_response(prompt)
    
    try:
        import json
        import re
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', llm_response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(llm_response)
    except:
        parsed = {
            "infection_flow": ["Initial access", "Execution", "Persistence", "Privilege escalation", "Data encryption"],
            "mitre_mapping": [{"id": "T1566", "name": "Phishing"}],
            "prevention_tips": ["Regular backups", "Security awareness training", "Email filtering"]
        }
    
    ransomware_data = RansomwareResponse(
        attack_vector=request.attack_vector,
        infection_flow=parsed.get('infection_flow', []),
        mitre_mapping=parsed.get('mitre_mapping', []),
        prevention_tips=parsed.get('prevention_tips', [])
    )
    
    doc = ransomware_data.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.ransomware_simulations.insert_one(doc)
    
    return ransomware_data

@api_router.post("/attack-scenario/generate", response_model=AttackScenarioResponse)
async def generate_attack_scenario(request: AttackScenarioRequest):
    prompt = f"""Generate a complete cyber attack scenario for training.

Organization Type: {request.organization_type}
Security Maturity: {request.security_maturity}

Provide:
1. Attack title
2. Timeline with 6-8 stages, each with: stage (name), time (relative time like 'Day 0', 'Week 1'), description, impact

Format as JSON with keys: title, timeline (array of objects)
[SIMULATION ONLY]"""

    llm_response = await get_llm_response(prompt)
    
    try:
        import json
        import re
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', llm_response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(llm_response)
    except:
        parsed = {
            "title": "Advanced Persistent Threat Simulation",
            "timeline": [
                {"stage": "Initial Access", "time": "Day 0", "description": "Phishing campaign", "impact": "Low"},
                {"stage": "Execution", "time": "Day 1", "description": "Malware execution", "impact": "Medium"}
            ]
        }
    
    scenario_data = AttackScenarioResponse(
        title=parsed.get('title', 'Cyber Attack Simulation'),
        timeline=parsed.get('timeline', [])
    )
    
    doc = scenario_data.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.attack_scenarios.insert_one(doc)
    
    return scenario_data

@api_router.post("/training/question", response_model=TrainingQuestionResponse)
async def generate_training_question(request: TrainingQuestionRequest):
    prompt = f"""Generate a cybersecurity training question.

Scenario Type: {request.scenario_type}

Provide:
1. A multiple-choice question
2. 4 options (A, B, C, D)
3. Correct answer (letter)
4. Detailed explanation

Format as JSON with keys: question, options (array of 4 strings), correct_answer (letter), explanation"""

    llm_response = await get_llm_response(prompt)
    
    try:
        import json
        import re
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', llm_response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(llm_response)
    except:
        parsed = {
            "question": "What is the first step in responding to a phishing email?",
            "options": ["Click the link", "Report to IT", "Reply to sender", "Delete immediately"],
            "correct_answer": "B",
            "explanation": "Always report suspicious emails to IT security team."
        }
    
    question_data = TrainingQuestionResponse(
        question=parsed.get('question', ''),
        options=parsed.get('options', []),
        correct_answer=parsed.get('correct_answer', 'A'),
        explanation=parsed.get('explanation', '')
    )
    
    return question_data

@api_router.post("/training/answer", response_model=TrainingAnswerResponse)
async def check_training_answer(request: TrainingAnswerRequest):
    # Retrieve question from database by ID
    # For MVP, simplified logic
    correct = request.user_answer in ['B', 'C']
    
    response = TrainingAnswerResponse(
        correct=correct,
        explanation="Good job!" if correct else "Review the material and try again.",
        score_gained=10 if correct else 0
    )
    
    # Store score
    await db.training_scores.insert_one({
        "question_id": request.question_id,
        "user_answer": request.user_answer,
        "correct": correct,
        "score": response.score_gained,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return response

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    phishing_count = await db.phishing_simulations.count_documents({})
    ransomware_count = await db.ransomware_simulations.count_documents({})
    scenario_count = await db.attack_scenarios.count_documents({})
    
    # Calculate total training score
    scores = await db.training_scores.find({}).to_list(1000)
    total_score = sum(s.get('score', 0) for s in scores)
    
    return DashboardStats(
        total_simulations=phishing_count + ransomware_count + scenario_count,
        phishing_sims=phishing_count,
        ransomware_sims=ransomware_count,
        attack_scenarios=scenario_count,
        training_score=total_score
    )


# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

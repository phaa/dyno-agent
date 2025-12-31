# 🎓 AI Engineering Mentorship Guide - Dyno Agent

> **Objetivo**: Transformar este projeto em uma vitrine profissional de AI Engineering que impressione recrutadores e demonstre expertise técnica completa.

---

## 📚 **FASE 1: CRITICAL FIXES (1-2 dias)**

### **🎯 Learning Objective**
Demonstrar capacidade de **debugging**, **data modeling** e **security** - habilidades essenciais para AI Engineers.

---

### **Task 1.1: Fix Vehicle Model (30 min)**

**🧠 Why This Matters:**
- Data consistency é fundamental em AI systems
- Mostra atenção a detalhes e debugging skills
- Demonstra conhecimento de database migrations

**📝 Step-by-Step:**

1. **Analyze the Problem:**
```bash
# Primeiro, entenda o problema
grep -r "weight_lbs" app/  # Veja onde é usado
grep -r "weight_class" app/  # Compare com o que existe
```

2. **Create Migration:**
```bash
make new-migration msg="add weight_lbs to vehicle model"
```

3. **Update Model:**
```python
# app/models/vehicle.py
class Vehicle(Base):
    # ... existing fields ...
    weight_lbs = Column(Integer, nullable=True)  # Add this
    weight_class = Column(String, nullable=True)  # Keep for compatibility
```

4. **Update Service Logic:**
```python
# app/services/allocation_service.py
# Replace weight_class logic with weight_lbs calculations
weight_class = "<10K" if vehicle.weight_lbs <= 10000 else ">10K"
```

**🎯 Pro Tips:**
- Always backup before migrations
- Test migration rollback
- Update seed data to include weight_lbs
- Add data validation (weight_lbs > 0)

**📊 Portfolio Value:**
- Shows database design skills
- Demonstrates migration management
- Proves debugging methodology

---

### **Task 1.2: Secure Chat Endpoint (15 min)**

**🧠 Why This Matters:**
- Security é crítico em AI applications
- Mostra understanding de authentication flows
- Demonstra production-ready thinking

**📝 Step-by-Step:**

1. **Add JWT Protection:**
```python
# app/main.py
@app.post("/chat/stream", dependencies=[Depends(JWTBearer())])
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
```

2. **Extract User from Token:**
```python
# app/auth/auth_bearer.py - Update to return user info
def verify_jwt(self, jwtoken: str) -> dict:
    try:
        payload = jwt.decode(jwtoken, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload  # Should contain user email
    except:
        return None
```

3. **Use Real User in Agent:**
```python
# In chat_stream function
user_email = request.user_email  # Add to ChatRequest schema
inputs = {
    "messages": [{"role": "user", "content": user_message}],
    "user_name": user_email.split("@")[0],  # Extract name from email
}
```

**🎯 Pro Tips:**
- Test with invalid tokens
- Add rate limiting per user
- Log authentication events
- Handle token expiration gracefully

**📊 Portfolio Value:**
- Demonstrates security awareness
- Shows JWT implementation skills
- Proves production mindset

---

### **Task 1.3: Add Input Validation (45 min)**

**🧠 Why This Matters:**
- Data quality é essencial para AI systems
- Mostra defensive programming
- Demonstra API design expertise

**📝 Step-by-Step:**

1. **Create Validators:**
```python
# app/schemas/validators.py
from pydantic import validator, Field
from datetime import date, timedelta

class AllocateRequest(BaseModel):
    weight_lbs: Optional[int] = Field(None, gt=0, le=80000)  # Reasonable vehicle weight
    start_date: date = Field(..., description="Test start date")
    end_date: date = Field(..., description="Test end date")
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    @validator('start_date')
    def not_in_past(cls, v):
        if v < date.today():
            raise ValueError('start_date cannot be in the past')
        return v
```

2. **Add Business Rules:**
```python
# app/services/validators.py
class BusinessRules:
    MAX_ALLOCATION_DAYS = 30
    MIN_ALLOCATION_DAYS = 1
    
    @staticmethod
    def validate_allocation_duration(start: date, end: date):
        duration = (end - start).days + 1
        if duration > BusinessRules.MAX_ALLOCATION_DAYS:
            raise ValueError(f"Allocation cannot exceed {BusinessRules.MAX_ALLOCATION_DAYS} days")
        if duration < BusinessRules.MIN_ALLOCATION_DAYS:
            raise ValueError(f"Allocation must be at least {BusinessRules.MIN_ALLOCATION_DAYS} day")
```

3. **Custom Exception Handler:**
```python
# app/exceptions.py
from fastapi import HTTPException
from fastapi.responses import JSONResponse

class ValidationError(Exception):
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": exc.message,
            "field": exc.field
        }
    )
```

**🎯 Pro Tips:**
- Use Pydantic's built-in validators
- Create reusable validation functions
- Add comprehensive error messages
- Test edge cases thoroughly

**📊 Portfolio Value:**
- Shows API design expertise
- Demonstrates data quality focus
- Proves error handling skills

---

## 📚 **FASE 2: CORE FEATURES (2-3 dias)**

### **🎯 Learning Objective**
Demonstrar **system design**, **data persistence** e **testing** - skills que separam junior de senior engineers.

---

### **Task 2.1: Implement Chat History (2 hours)**

**🧠 Why This Matters:**
- Conversational AI precisa de context persistence
- Mostra database design para AI applications
- Demonstra user experience thinking

**📝 Step-by-Step:**

1. **Design Conversation Schema:**
```python
# app/models/conversation.py
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)  # UUID
    user_email = Column(String, ForeignKey("users.email"))
    title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    messages = relationship("Message", back_populates="conversation")
    user = relationship("User")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="messages")
```

2. **Create Conversation Service:**
```python
# app/services/conversation_service.py
class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create_conversation(self, user_email: str, conversation_id: str = None):
        if conversation_id:
            conv = await self.db.get(Conversation, conversation_id)
            if conv and conv.user_email == user_email:
                return conv
        
        # Create new conversation
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_email=user_email,
            title="New Chat"
        )
        self.db.add(conv)
        await self.db.flush()
        return conv
    
    async def save_message(self, conversation_id: str, role: str, content: str):
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        self.db.add(message)
        await self.db.commit()
        return message
    
    async def get_conversation_history(self, conversation_id: str, limit: int = 50):
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(reversed(result.scalars().all()))
```

3. **Update Chat Endpoint:**
```python
# app/main.py
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: str = Depends(get_current_user)):
    conv_service = ConversationService(db)
    
    # Get or create conversation
    conversation = await conv_service.get_or_create_conversation(
        user_email=current_user,
        conversation_id=request.conversation_id
    )
    
    # Save user message
    await conv_service.save_message(conversation.id, "user", request.message)
    
    # Get conversation history for context
    history = await conv_service.get_conversation_history(conversation.id)
    
    # Build messages with history
    messages = [{"role": msg.role, "content": msg.content} for msg in history]
    messages.append({"role": "user", "content": request.message})
    
    # ... rest of streaming logic ...
    
    # Save assistant response after streaming
    await conv_service.save_message(conversation.id, "assistant", full_response)
```

**🎯 Pro Tips:**
- Use UUIDs for conversation IDs
- Implement conversation title auto-generation
- Add conversation search functionality
- Consider message compression for long chats

**📊 Portfolio Value:**
- Shows conversational AI expertise
- Demonstrates database design for AI
- Proves user experience focus

---

### **Task 2.2: Comprehensive Testing Suite (3 hours)**

**🧠 Why This Matters:**
- Testing é fundamental para production AI systems
- Mostra engineering discipline
- Demonstra quality assurance mindset

**📝 Step-by-Step:**

1. **Setup Test Infrastructure:**
```python
# app/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

2. **Test Business Logic:**
```python
# app/tests/test_allocation_service.py
import pytest
from datetime import date, timedelta
from app.services.allocation_service import AllocationService
from app.models.vehicle import Vehicle
from app.models.dyno import Dyno

class TestAllocationService:
    @pytest.mark.asyncio
    async def test_find_available_dynos_success(self, db_session):
        # Setup test data
        dyno = Dyno(
            name="Test Dyno",
            supported_weight_classes=["<10K"],
            supported_drives=["2WD"],
            supported_test_types=["brake"],
            enabled=True
        )
        db_session.add(dyno)
        await db_session.commit()
        
        service = AllocationService(db_session)
        
        # Test
        result = await service.find_available_dynos_core(
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            weight_lbs=5000,
            drive_type="2WD",
            test_type="brake"
        )
        
        # Assert
        assert len(result) == 1
        assert result[0]["name"] == "Test Dyno"
    
    @pytest.mark.asyncio
    async def test_auto_allocate_vehicle_success(self, db_session):
        # Setup
        vehicle = Vehicle(vin="TEST123", weight_lbs=5000, drive_type="2WD")
        dyno = Dyno(
            name="Test Dyno",
            supported_weight_classes=["<10K"],
            supported_drives=["2WD"],
            supported_test_types=["brake"],
            enabled=True
        )
        db_session.add_all([vehicle, dyno])
        await db_session.commit()
        
        service = AllocationService(db_session)
        
        # Test
        result = await service.auto_allocate_vehicle_core(
            vehicle_id=vehicle.id,
            start_date=date.today(),
            days_to_complete=1
        )
        
        # Assert
        assert result["success"] is True
        assert "allocation" in result
```

3. **Test API Endpoints:**
```python
# app/tests/test_api.py
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_register_user_success(client):
    user_data = {
        "email": "test@example.com",
        "fullname": "Test User",
        "password": "testpass123"
    }
    response = client.post("/register", json=user_data)
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_allocate_endpoint_success(client, auth_headers):
    allocation_data = {
        "weight_lbs": 5000,
        "drive_type": "2WD",
        "test_type": "brake",
        "start_date": "2024-01-15",
        "end_date": "2024-01-16"
    }
    response = client.post("/allocate", json=allocation_data, headers=auth_headers)
    assert response.status_code == 200
```

4. **Test Agent Tools:**
```python
# app/tests/test_agent_tools.py
import pytest
from app.agents.tools import find_available_dynos, auto_allocate_vehicle

class TestAgentTools:
    @pytest.mark.asyncio
    async def test_find_available_dynos_tool(self, mock_runtime):
        # Mock the runtime context
        with mock_runtime:
            result = await find_available_dynos(
                start_date=date.today(),
                end_date=date.today() + timedelta(days=1),
                weight_lbs=5000,
                drive_type="2WD",
                test_type="brake"
            )
            assert isinstance(result, list)
```

**🎯 Pro Tips:**
- Use pytest fixtures for test data
- Mock external dependencies (LLM calls)
- Test both success and failure scenarios
- Measure test coverage (aim for >80%)
- Use factory patterns for test data creation

**📊 Portfolio Value:**
- Demonstrates testing expertise
- Shows quality assurance mindset
- Proves production-ready code

---

### **Task 2.3: Refactor main.py into Routers (1 hour)**

**🧠 Why This Matters:**
- Code organization é crucial para maintainability
- Mostra software architecture skills
- Demonstra scalability thinking

**📝 Step-by-Step:**

1. **Create Router Structure:**
```python
# app/routers/__init__.py
# app/routers/auth.py
# app/routers/chat.py
# app/routers/allocation.py
# app/routers/health.py
```

2. **Auth Router:**
```python
# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.schemas.user import UserSchema, UserLoginSchema

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register")
async def register_user(user: UserSchema, db: AsyncSession = Depends(get_db)):
    # Move registration logic here
    pass

@router.post("/login")
async def login_user(user: UserLoginSchema, db: AsyncSession = Depends(get_db)):
    # Move login logic here
    pass
```

3. **Update main.py:**
```python
# app/main.py
from fastapi import FastAPI
from app.routers import auth, chat, allocation, health

app = FastAPI(title="Dyno Allocator API", lifespan=lifespan)

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(allocation.router)

# Keep only root endpoint
@app.get("/")
def hello():
    return {"message": "Hello, World!"}
```

**🎯 Pro Tips:**
- Group related endpoints in same router
- Use consistent naming conventions
- Add router-level dependencies
- Document each router's purpose

**📊 Portfolio Value:**
- Shows code organization skills
- Demonstrates scalability thinking
- Proves maintainability focus

---

## 📚 **FASE 3: PRODUCTION POLISH (1-2 dias)**

### **🎯 Learning Objective**
Demonstrar **production readiness**, **monitoring** e **deployment** - skills que mostram seniority.

---

### **Task 3.1: Enhanced Error Handling (1 hour)**

**🧠 Why This Matters:**
- Error handling é crucial para user experience
- Mostra defensive programming
- Demonstra production mindset

**📝 Step-by-Step:**

1. **Custom Exception Classes:**
```python
# app/exceptions.py
class DynoAgentException(Exception):
    """Base exception for Dyno Agent"""
    pass

class VehicleNotFoundError(DynoAgentException):
    """Raised when vehicle is not found"""
    pass

class NoAvailableDynosError(DynoAgentException):
    """Raised when no dynos are available"""
    pass

class AllocationConflictError(DynoAgentException):
    """Raised when allocation conflicts occur"""
    pass
```

2. **Global Exception Handlers:**
```python
# app/main.py
@app.exception_handler(VehicleNotFoundError)
async def vehicle_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Vehicle Not Found",
            "message": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

**📊 Portfolio Value:**
- Shows error handling expertise
- Demonstrates user experience focus
- Proves production readiness

---

### **Task 3.2: Logging & Monitoring (45 min)**

**🧠 Why This Matters:**
- Observability é essencial para production systems
- Mostra operational awareness
- Demonstra debugging capabilities

**📝 Step-by-Step:**

1. **Structured Logging:**
```python
# app/core/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        return json.dumps(log_entry)

def setup_logging():
    logger = logging.getLogger("dyno_agent")
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

2. **Request Logging Middleware:**
```python
# app/middleware/logging.py
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(
            "Request processed",
            extra={
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "process_time": process_time
            }
        )
        
        return response
```

**📊 Portfolio Value:**
- Shows operational awareness
- Demonstrates monitoring skills
- Proves production experience

---

### **Task 3.3: API Documentation (30 min)**

**🧠 Why This Matters:**
- Documentation é crucial para API adoption
- Mostra communication skills
- Demonstra user-centric thinking

**📝 Step-by-Step:**

1. **Enhanced OpenAPI Docs:**
```python
# app/main.py
app = FastAPI(
    title="Dyno Agent API",
    description="Intelligent vehicle dynamometer allocation system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
```

2. **Detailed Endpoint Documentation:**
```python
# app/routers/allocation.py
@router.post(
    "/allocate",
    response_model=AllocationOut,
    summary="Allocate dyno for vehicle test",
    description="Automatically finds and allocates an available dyno for vehicle testing",
    responses={
        200: {"description": "Allocation successful"},
        404: {"description": "No available dynos found"},
        409: {"description": "Allocation conflict occurred"}
    }
)
async def allocate_dyno(req: AllocateRequest):
    pass
```

**📊 Portfolio Value:**
- Shows documentation skills
- Demonstrates API design expertise
- Proves user-centric thinking

---

## 🏆 **PORTFOLIO PRESENTATION TIPS**

### **📋 README Structure for Recruiters:**
1. **Problem Statement** (30 seconds to hook them)
2. **Architecture Diagram** (visual impact)
3. **Key Features** (bullet points)
4. **Tech Stack** (buzzwords they're looking for)
5. **Demo Links** (live deployment)
6. **Code Highlights** (show your best work)

### **🎯 Key Selling Points:**
- **Modern AI Stack**: LangGraph, FastAPI, async/await
- **Production Ready**: Testing, logging, error handling
- **Scalable Architecture**: Microservices patterns
- **Security First**: JWT, input validation, SQL injection prevention
- **Cloud Native**: Docker, Terraform, AWS deployment

### **📊 Metrics to Highlight:**
- Test coverage percentage
- API response times
- Code quality scores
- Documentation completeness

### **🚀 Demo Script:**
1. Show chat interface working
2. Demonstrate dyno allocation
3. Show error handling
4. Highlight code organization
5. Explain architecture decisions

---

## 💡 **FINAL ADVICE**

**Remember:** Recruiters spend 30 seconds on your GitHub. Make those seconds count:

1. **Visual Impact**: Architecture diagrams, screenshots
2. **Clear Value**: Solve a real problem
3. **Technical Depth**: Show advanced concepts
4. **Production Quality**: Tests, docs, deployment
5. **Personal Touch**: Your engineering decisions and learnings

**You're not just building a project - you're telling a story of your engineering journey. Make it compelling! 🚀**
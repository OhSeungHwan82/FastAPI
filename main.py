from fastapi import FastAPI
from starlette.requests import Request
from starlette.middleware.cors import CORSMiddleware
import uvicorn
import logging
from fastapi.openapi.utils import get_openapi

from app.routers.suikmanage import suikmanage_router
from app.routers.incarInfo  import incarInfo_router
from app.routers.insuproductcompare import insuproductcompare_router
from app.routers.giteaApi import giteaApi_router
from app.routers.devSample import devSample_router
from app.routers.userInfo import userInfo_router
from app.routers.ledgerDatabase import ledgerDatabase_router
from app.routers.dbe import dbe_router
from app.routers.public import public_router

from apscheduler.schedulers.background import BackgroundScheduler
from app.service.scheduled_task import scheduled_task

app = FastAPI()

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_app_root():
    return {"message": "Hello from App"}
#####################원장변경 스케줄러#############################
scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_task, 'interval', minutes=1)
##################################################################

#################################### docs 구성 변경##########################################################
####### 추가 문서 탭을 포함한 전체 문서 생성 ###
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="INCAR API",
        version="1.0.0",
        description="This documentation describes the INCAR API.",
        routes=app.routes,
    )
    openapi_schema["info"]["x-tagGroups"] = [
        {"name": "Default", "tags": ["default"]},
		{"name": "suikManage", "tags": ["suikManage"]},
        {"name": "giteaApi", "tags": ["giteaApi"]},
		{"name": "devSample", "tags": ["devSample"]},
        {"name": "ledgerDatabase", "tags": ["ledgerDatabase"]},
        {"name": "public", "tags": ["public"]},
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Custom OpenAPI 문서 라우터 등록
app.openapi = custom_openapi#
app.redoc_url = None  # ReDoc 비활성화

app.include_router(suikmanage_router.router, tags=["suikManage"])
app.include_router(giteaApi_router.router, tags=["giteaApi"])
app.include_router(devSample_router.router, tags=["devSample"])
app.include_router(userInfo_router.router, tags=["userInfo"])
app.include_router(ledgerDatabase_router.router, tags=["ledgerDatabase"])

app.include_router(insuproductcompare_router.router)
app.include_router(incarInfo_router.router)
app.include_router(dbe_router.router, tags=["dbe"])
app.include_router(public_router.router, tags=["public"])

#################################### 처리중인 요청수 확인 및 로그################################################
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
	app.state.active_requests += 1  # 현재 처리 중인 요청의 수를 1 증가시킴
	response = await call_next(request)
	app.state.active_requests -= 1  # 현재 처리 중인 요청의 수를 1 감소시킴
	return response

@app.get("/stats")
async def stats():
	return {"active_requests": app.state.active_requests}

@app.on_event("startup")
async def startup_event() :
    scheduler.start()
    app.state.active_requests = 0  # 초기화
    access_log() 
    

@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()

def access_log() :
    logger = logging.getLogger('uvicorn.access')
    console_formatter = uvicorn.logging.ColourizedFormatter(
        "{asctime} - {message}",
        style="{", use_colors=True)
    handler = logging.handlers.TimedRotatingFileHandler(filename="./logs/fastapi.log", when='midnight', interval=1, backupCount=100)
    handler.setFormatter(console_formatter)
    logger.addHandler(handler)

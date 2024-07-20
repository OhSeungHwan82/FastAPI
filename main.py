from fastapi import FastAPI
from starlette.requests import Request
from starlette.middleware.cors import CORSMiddleware
import uvicorn
import logging
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
from pathlib import Path
from starlette.exceptions import HTTPException

from app.routers.suikmanage import suikmanage_router
from app.routers.incarInfo  import incarInfo_router
from app.routers.insuproductcompare import insuproductcompare_router
from app.routers.giteaApi import giteaApi_router
from app.routers.devSample import devSample_router
from app.routers.userInfo import userInfo_router
from app.routers.ledgerDatabase import ledgerDatabase_router
from app.routers.dbe import dbe_router
from app.routers.public import public_router
from app.routers.batchJob import batchJob_router
from app.routers.commcode import commcode_router

from apscheduler.schedulers.background import BackgroundScheduler
from app.service.scheduled_task import scheduled_task, batchJob_scheduled_task, cronJob_scheduled_task

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/openapi.json")
async def get_open_api():
    return get_openapi(title="My API", version="0.1.0", routes=app.routes)

@app.get("/swagger", include_in_schema=False)
async def custom_swagger_ui_html():
    # path = os.getcwd()
    # print(f"path:{path}")
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Custom Swagger UI</title>
        <link href="/static/swagger-ui.css" rel="stylesheet">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="/static/swagger-ui-bundle.js"></script>
        <script>
        const ui = SwaggerUIBundle({{
            url: '/openapi.json',
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis
            ],
            layout: "BaseLayout"
        }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

    # return {"message": os.getcwd()}
    # return get_swagger_ui_html(
    #     openapi_url="/openapi.json",
    #     title="Custom docs",
    #     swagger_ui_js_url="/static/swagger-ui-bundle.js",
    #     swagger_ui_css_url="/static/swagger-ui.css"
    # )

# @app.get("/redoc", include_in_schema=False)
# async def custom_redoc_html():
#     return get_redoc_html(
#         openapi_url="/openapi.json",
#         title="Custom ReDoc",
#         redoc_js_url="/static/redoc.standalone.js"
#     )

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
    return {"message": "Hello from App."}
#####################원장변경 스케줄러#############################
scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_task, 'interval', minutes=5)
##################################################################
#####################배치관리 스케줄러#############################
#scheduler.add_job(batchJob_scheduled_task, 'interval', minutes=5)
##################################################################
#####################Cron관리 스케줄러#############################
scheduler.add_job(cronJob_scheduled_task, 'interval', minutes=1)
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
        {"name": "batchJob", "tags": ["batchJob"]},
        {"name": "commcode", "tags": ["commcode"]},
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
app.include_router(batchJob_router.router, tags=["batchJob"])
app.include_router(insuproductcompare_router.router)
app.include_router(incarInfo_router.router)
app.include_router(dbe_router.router, tags=["dbe"])
app.include_router(public_router.router, tags=["public"])
app.include_router(commcode_router.router, tags=["commcode"])

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

# def check_static_dir():
#     # 현재 작업 디렉토리에 `static` 폴더가 있는지 확인
#     static_dir = Path("static")
#     if not static_dir.is_dir():
#         raise HTTPException(status_code=500, detail="Static directory not found")

@app.on_event("startup")
async def startup_event() :
    # check_static_dir()
    scheduler.start()
    app.state.active_requests = 0  # 초기화
    access_log() 
    error_log()

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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 여기에서 exc 객체를 사용하여 오류 내용을 자세히 분석할 수 있습니다.
    # 예를 들어, 오류 메시지와 함께 어떤 필드에서 오류가 발생했는지 클라이언트에게 알려줄 수 있습니다.
    errors = {"errors": exc.errors(), "detail": "입력값 검증에 실패했습니다."}
    return JSONResponse(status_code=422, content=errors)    

import requests
def send_slack_notification(message, slack_webhook_url):
    payload = {
        "text": message
    }

    response = requests.post(slack_webhook_url, json=payload)

    if response.status_code == 200:
        print("Slack notification sent successfully")
    else:
        print(f"Failed to send Slack notification. Status code: {response.status_code}")

class SlackNotificationHandler(logging.Handler):
    def __init__(self, slack_webhook_url):
        super().__init__()
        self.slack_webhook_url = slack_webhook_url

    def emit(self, record):
        log_entry = self.format(record)
        send_slack_notification(log_entry, self.slack_webhook_url)

def error_log():
    error_logger = logging.getLogger('uvicorn.error')
    error_logger.setLevel(logging.ERROR)

    error_file_formatter = logging.Formatter("{asctime} - {message}", style="{")
    error_file_handler = logging.handlers.TimedRotatingFileHandler(
        filename="./logs/uvicorn_error.log",
        when='midnight',
        interval=1,
        backupCount=100
    )
    error_file_handler.setFormatter(error_file_formatter)
    error_logger.addHandler(error_file_handler)

    slack_handler = SlackNotificationHandler('https://hooks.slack.com/services/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')
    slack_handler.setLevel(logging.ERROR)
    slack_handler.setFormatter(error_file_formatter)

    error_logger.addHandler(slack_handler)

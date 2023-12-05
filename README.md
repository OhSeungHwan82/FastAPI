# FastAPI 환경구성.

## 1. cx_Oracle 를 설치 FastAPI 사용
  FastAPI uvicorn cx_Oracle 설치
    pip install fastapi
    pip install "uvicorn[standard]"
    pip install cx_Oracle
  
  Oracle Client library 버전 오류 시
  https://www.oracle.com/kr/database/technologies/instant-client/winx64-64-downloads.html
  해당 사이트에서 패키지를 다운로드 
  orcl.py 에 cx_Oracle.init_oracle_client(lib_dir=r"D:\instantclient_21_9") 추가
## 2. VSCode 에서 가상환경 
  작업할 경로로 이동
    cd IncarFastAPI
  가상환경 설치
    python -m venv venv_fastAPI
    source venv_fastAPI/Scripts/activate.bat
## 3. 가상환경에서 FastAPI 설치
  가상환경이 설치된 vene_fastAPI로 이동
    cd vene_fastAPI
  FastAPI 설치
    pip install fastapi
  fastapi framework만으로는 웹 개발을 할 수 없고, ASGI와 호환되는 웹 서버가 필요함

  uvicorn은 비동기 방식의 http server -> ASC
    pip install "uvicorn[standard]"
  uvicorn Start 시작전 main.py 파일을 생성해야함
    uvicorn main:app --reload

## 4. DataBase 접속 환경구성
  Python 프로그램에서 Oracle Database 에 접속해서 DB 작업을 할 수 있도록 도와주는 라이브러리에 cx_Oracle 과 python-oracledb 가 있음

  cx_Oracle 이 버전업을 하면서 이름을 python-oracledb 바뀌었고 Window 환경에서는 python-oracledb 만 가능
  
  https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html
    python -m pip install oracledb --upgrade
## 5. API 문서 제공
  http://localhost:8000/docs


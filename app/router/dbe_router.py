# -*- coding: utf-8 -*-
import requests
import sys
import time
from fastapi import APIRouter, FastAPI, Body, Query, HTTPException, Request, Depends
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.requests import Request
import pdfkit
import tempfile
from io import BytesIO
from datetime import datetime
import subprocess
import os  # os 모듈 임포트 추가
import shutil

from app.routers.userInfo import security as sc
from app.service.user import UserService
from app.database.postgre import PostgreLink
from pydantic import BaseModel
from pydantic import Field
from app.database.new_orcl import New19DB
from app.database.orcl import DbLink

from typing import Optional
from urllib.parse import unquote, parse_qs
import json
 
router = APIRouter(
    prefix="/api/dbe", 
)

@router.post("/srm", name="작업시간 입력", description="IIMS 작업시간을 DB에 저장한다")
async def srm_post(request: Request):
    # GET 요청에서 넘어온 값을 확인
    query_params = request.query_params

    r_url = query_params.get("r_uri_name")
    r_server_name = query_params.get("r_server_name")

    # POST 데이터 읽기
    post_data = await request.body()
    post_data_str = post_data.decode("utf-8")

    decoded_data = unquote(post_data_str)

    # parse_qs 함수를 사용하여 쿼리 스트링 파라미터를 딕셔너리로 파싱
    parsed_data = parse_qs(decoded_data)

    r_headers_dict = {}

    for key, value in parsed_data.items():
        if key.startswith('r_headers['):
            new_key = key.split('[')[1].split(']')[0]
            r_headers_dict[new_key] = value

    header_dict_as_string = str(r_headers_dict)

    r_pid = parsed_data.get("r_pid", [""])[0]
    r_memory_usage = parsed_data.get("r_memory_usage", [""])[0]
    r_memory_peak_usage_false = parsed_data.get("r_memory_peak_usage_false", [""])[0]
    r_memory_peak_usage_true = parsed_data.get("r_memory_peak_usage_true", [""])[0]
    r_exec_time = parsed_data.get("r_exec_time", [""])[0]
    r_start_time = parsed_data.get("r_start_time", [""])[0]
    r_finsh_time = parsed_data.get("r_finsh_time", [""])[0]
    r_server_addr = parsed_data.get("r_server_addr", [""])[0]

    # DB에 저장
    pdb = PostgreLink()

    try:
        qry = """insert into dbe.elog_srm
                        (
                             pid
                            ,memory_usage
                            ,memory_peak_usage_false
                            ,memory_peak_usage_true
                            ,exec_time
                            ,start_time
                            ,finsh_time
                            ,server_addr
                            ,server_name
                            ,uri
                            ,header
                        )
            values
                        (
                             %s
                            ,%s
                            ,%s
                            ,%s
                            ,%s
                            ,to_timestamp(%s, 'YYYYMMDDHH24MISS')
                            ,to_timestamp(%s, 'YYYYMMDDHH24MISS')
                            ,%s
                            ,%s
                            ,%s
                            ,%s
                        )
        """
        params = (r_pid, r_memory_usage, r_memory_peak_usage_false, r_memory_peak_usage_true, r_exec_time, r_start_time, r_finsh_time, r_server_addr, r_server_name, r_url, header_dict_as_string)

        #print(params)
        #print(qry)
        
        pdb.execute_bind(qry, params)
        pdb.commit()

    except Exception as e:
        print("Error:", e)
        # 롤백
        pdb.rollback()
    finally:
        # 연결 닫기
        pdb.cursor_close()
        pdb.close()


    return {"result_code": "1000", "result_msg": "ok"}

###########################################################################################################
class NewPassword(BaseModel):
    sawon_cd: str
    password: str

@router.post("/setNewPassword", name="새패스워드저장", description="새 패스워드를 저장한다")
async def set_new_password_post(newPassword: NewPassword):
    # POST 데이터 읽기
    sawon_cd = newPassword.sawon_cd;
    password = newPassword.password;

    db = New19DB()

    qry = """
        select CryptIT2.encrypt(:password, :key) from dual
    """
    qry = """
        select xx1.dec_varchar2_sel(:password, 10,:key) from dual
    """
    qry = """
        select xx1.enc_varchar2_ins(:password, 10,:key) from dual
    """
    bind_arr = {"password":password, "key":"INCAR_S001"}

    db.execute(qry , bind_arr)
    
    fields = db.get_field_names()
    datas = db.get_datas()

    new_password = ''

    for data in datas:
        new_password = data[0]
    print("new_password",new_password)
    db.close()

    ## 현재 PDB_ONE에 연결해서 저장한다.

    db = DbLink()

    qry = """
        MERGE INTO new_password np
        USING (SELECT :sawon_cd AS sawon_cd, :password AS new_password_value FROM dual) data
            ON (np.sawon_cd = data.sawon_cd)
        WHEN MATCHED THEN
              UPDATE SET np.password = data.new_password_value
        WHEN NOT MATCHED THEN
              INSERT (np.sawon_cd, np.password)
              VALUES (data.sawon_cd, data.new_password_value)
    """
    bind_arr = {"sawon_cd":sawon_cd, "password":new_password}

    db.execute(qry , bind_arr)
    
    db.commit()
    db.close()

    return {"result_code": "1000", "result_msg": "ok"}

#############################################################################
@router.post("/make", name="FILE MAKE", description="HTML to PDF")
async def html_to_pdf(request: Request):
    try:
        form_data = await request.form()
        html = form_data.get("html")

        output_dir = "/home/incar/pdf"

        # HTML을 임시 파일에 저장
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as html_file:
            html_file.write('<cfprocessingdirective pageEncoding=\"utf-8\"><cfdocument backgroundVisible=\"yes\" permissions=\"AllowPrinting\" unit=\"cm\" marginTop=\"0\" marginBottom=\"0\" marginLeft=\"0.2\" marginRight=\"0.2\" format=\"PDF\" pageType=\"A4\">')
            html_file.write(html.encode("utf-8"))
        
        # 현재 날짜와 시간 정보를 얻음 (년월일시분초)
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S%f")
        
        # PDF 파일명을 설정
        pdf_filename = f"print_{current_datetime}.pdf"

        # Xvfb를 사용하여 wkhtmltopdf를 실행
        pdf_file_path = html_file.name.replace(".html", ".pdf")
        xvfb_cmd = f'xvfb-run -a wkhtmltopdf --dpi 300 --page-size A4 --margin-top 0 --margin-right 0 --margin-bottom 0 --margin-left 0 {html_file.name} {pdf_file_path}'
        subprocess.run(xvfb_cmd, shell=True)

        output_file_path = os.path.join(output_dir, pdf_filename)
        shutil.move(pdf_file_path, output_file_path)

        # XML 응답 생성
        xml_response = f"""<?xml version="1.0" encoding="utf-8"?>
        <root>
          <status>
            <ercode>0</ercode>
            <ermsg><![CDATA[OK]]></ermsg>
          </status>
          <object>
            <filename>{pdf_filename}</filename>
          </object>
        </root>
        """

        # XML 응답을 클라이언트에게 반환
        response = Response(content=xml_response, media_type="text/xml; charset=utf-8")
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PrintItem(BaseModel):
    filename: str

@router.get("/print", name="PDF DOWNLOAD", description="PDF DOWNLOAD")
async def download_file(filename:str):

    output_dir = "/home/incar/pdf"
    output_file_path = os.path.join(output_dir, filename)

    # 파일이 존재하는지 확인
    if not os.path.exists(output_file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # 파일을 클라이언트에게 반환
    response = FileResponse(output_file_path, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    # 파일을 전송한 후 파일 삭제
    #os.remove(output_file_path)

    return response

@router.post("/votm", name="votm 생성", description="votm을 리턴한다")
async def set_new_password_post(request: Request):
    form_data = await request.form()

    # 만약 form-data로 넘어온 경우
    votm_value = form_data.get('votm')

    db = New19DB()

    qry = """
        select xx1.enc_varchar2_ins(:password, 10,:key) from dual
    """
    bind_arr = {"password":votm_value, "key":"INCAR_S001"}

    db.execute(qry , bind_arr)
    
    fields = db.get_field_names()
    datas = db.get_datas()

    new_password = ''

    for data in datas:
        new_password = data[0]
    db.close()

    return new_password

################################
@router.post("/elog", name="로그 입력", description="IIMS 로그를 DB에 저장한다")
async def elog_post(request: Request):
    # GET 요청에서 넘어온 값을 확인
    query_params = request.query_params
    r_uri_name = query_params.get("r_uri_name")
    r_regist_cd = query_params.get("r_regist_cd")
    r_server_name = query_params.get("r_server_name")
    r_remote_addr = query_params.get("r_remote_addr")
    
    # POST 데이터 읽기
    post_data = await request.body()
    post_data_str = post_data.decode("utf-8")

    decoded_data = unquote(post_data_str)

    # parse_qs 함수를 사용하여 쿼리 스트링 파라미터를 딕셔너리로 파싱
    parsed_data = parse_qs(decoded_data)

    r_uri_time = parsed_data.get("r_uri_time", [""])[0]
    r_pid = parsed_data.get("r_pid", [""])[0]

    # 딕셔너리를 JSON 포맷으로 변환
    json_data = json.dumps(parsed_data)

    # DB에 저장
    pdb = PostgreLink()

    try:
        qry = """insert into dbe.elog
                        (
                             uri
                            ,time
                            ,regist_cd
                            ,remote_addr
                            ,server_name
                            ,post
                            ,pid
                        )
            values
                        (
                             %s
                            ,to_timestamp(%s, 'YYYYMMDDHH24MISS')
                            ,%s
                            ,%s
                            ,%s
                            ,%s
                            ,%s
                        )
        """
        params = (r_uri_name, r_uri_time, r_regist_cd, r_remote_addr, r_server_name, json_data, r_pid)
        
        pdb.execute_bind(qry, params)
        pdb.commit()
       
    except Exception as e:
        print("Error:", e)
        # 롤백
        pdb.rollback()
    finally:
        # 연결 닫기
        pdb.close()


    return {"result_code": "1000", "result_msg": "ok"}

#######################################################################
@router.get("/elog", name="elog 조회", description="IIMS ELOG를 조회 한다.", status_code=200)
def elog_get(
    uri: str = Query(None,description="URI입력"),
    s_date: str = Query(None,description="조회일자"),
    s_time_start: str = Query(None,description="조회시간시작"),
    s_time_end: str = Query(None,description="조회시간종료"),
    pid: str = Query(None, description="PID"),
    content: str = Query(None, description="내용"),
    access_token:str=Depends(sc.get_access_token),
    user_service:UserService=Depends(UserService),
):
    code:dict = user_service.decode_jwt(access_token=access_token)

    if not uri:
        raise HTTPException(status_code=404, detail="URI Not Found")
    
    if not s_date:
        raise HTTPException(status_code=404, detail="DATE Not Found")
    
    if s_time_start:
        s_time_start = s_time_start[0:2]+":"+s_time_start[2:4]+":00"

    if s_time_end:
        s_time_end = s_time_end[0:2]+":"+s_time_end[2:4]+":59"

    qry_add = ""
    if pid:
        qry_add = qry_add + " and e.pid = '" + pid + "' "

    if not content:
        content = ""

    content = "%" + content + "%"

    temp_s_time = s_date + " " + s_time_start
    temp_e_time = s_date + " " + s_time_end
    
    pdb = PostgreLink()
    list_field =[]
    pdatas=[]
    params=[]
    try:
        qry = f"""
                select       uri || time as id
                        ,    uri
                        ,    time
                        ,    regist_cd 
                        ,    remote_addr
                        ,    server_name
                        ,    pid
                        ,    post
                from   dbe.elog_{s_date[0:6]} e 
                where  e.uri = %s
                and    e.time between %s and %s
                and    e.post like %s
                {qry_add}
        """
        qry += " order by e.time desc"
        params.extend([uri, temp_s_time, temp_e_time, content])
            
        print("qry:",qry)
        print("params:", params)
        pdb.execute_bind(qry , params)
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    results = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
    pdb.close()

    return results

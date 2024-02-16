# -*- coding: utf-8 -*-
from fastapi import APIRouter, Body, Query, Depends, HTTPException, File, UploadFile, Form
from app.database.postgre import PostgreLink
from psycopg2 import Error as PsycopgError
from app.database.orcl import DbLink
from cx_Oracle import DatabaseError as OracleError
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from app.models.batchJobModels import CreateJobTempleate, UpdateJobTempleate, CreateJobRequest
from app.service.user import UserService
from app.routers.userInfo import security as sc
from decimal import Decimal
import json
import sys
import os
from datetime import datetime, date
import requests
import xml.etree.ElementTree as ET
import time
import shutil
import csv

def default_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    raise TypeError("Type not serializable")

router = APIRouter(
    prefix="/api/batchJob",
)

def getSawonName(sawon_cd):
    db = DbLink()
    try:
        qry = """select name_kor sawon_nm from sawon where sawon_cd = :sawon_cd"""
        bind_arr = {"sawon_cd":sawon_cd}

        db.execute(qry , bind_arr)

        fields = db.get_field_names()
        datas = db.get_datas()
        print(datas)
        sawon_nm = datas[0][0]
        db.close()
    except OracleError as e:
        print("예외발생1",e)
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
    return sawon_nm

def createjob(execution_script, job_name):
    jenkins_url = 'http://10.16.16.180:8080/'
    jenkins_user = 'incar'
    jenkins_token = '11ae9647a7cb4a55f1392d92ea4a0d04dd'
	
    api_url = f'{jenkins_url}/createItem'
    headers = {
        'Content-Type': 'application/xml',
    }

    # 새로운 Job의 구성 XML 생성
    new_job_name = job_name
    new_job_xml = f"""
    <project>
    <builders>
        <hudson.tasks.Shell>
        <command>{execution_script}</command>
        </hudson.tasks.Shell>
    </builders>
    </project>
    """

    # Job 생성 요청 보내기
    response = requests.post(
        api_url,
        auth=(jenkins_user, jenkins_token),
        headers=headers,
        params={'name': new_job_name},
        data=new_job_xml
    )

    # 응답 확인
    if response.status_code == 200:
        print(f'Job "{new_job_name}"이 성공적으로 생성되었습니다.')
    else:
        print(f'Job 생성 중 오류가 발생했습니다. 응답 코드: {response.status_code}, 내용: {response.text}')
    return response.status_code

@router.get("/jobTemplates", name="배치관리 작업목록 조회", description="", status_code=200)
def getlist(
    gubun: str = Query(...,description="gubun=0은 선택안함, gubun=1은 수수료, gubun=2는 일반", enum=[0,1,2]),
	search: str = Query(None,description="search는 gubun에 선택한 값에 해당하는 검색내용을 입력"),
	page: int = Query(1,description="선택 페이지"),
	limit: int = Query(10,description="화면에 보여줄 갯수"),
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:dict = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")

    pdb = PostgreLink()
    list_field =[]
    pdatas=[]
    params=[]
    try:
        qry = f"""
            select	a.pk as id
                    , a.name
                    , a.gubun
                    , c.code_nm as gubun_nm
                    , a.status
                    , b.code_nm as status_nm
                    , a.use_yb
                    , to_char(a.update_date,'YYYY-MM-DD HH24:MI:SS') as update_date
                    , a.update_name
            from	job.job_templates a 
            inner join public.commcode b 
            on 		a.status  = b.code_id 
            inner join public.commcode c
            on 		a.status  = c.code_id 
            where 	b.cl_code = 11
            and 	c.cl_code = 12
            and		a.use_yb = '1'   
			"""
        # if status != "0":
        #     qry += " and a.status = %s "
        #     params.append(status)
        if gubun!="" and gubun != "0":
            qry += " and a.gubun = %s "
            params.append(gubun)
        if search!="":
            qry += " and name like %s "
            search = "%"+search+"%"
            params.append(search)

        qry += " order by a.pk desc limit %s offset (%s - 1) * %s"
        params.extend([limit, page, limit])
			
        pdb.execute_bind(qry , params)
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

    results = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
    pdb.close()

    return results
	
@router.get("/jobTemplates/{jt_pk}", name="배치관리 작업목록 상세화면", description="", status_code=200)
def getdetail(
	jt_pk: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")
    pdb = PostgreLink()
    pdatas=[]
    list_field1 =[]
    list_field2 =[]
    try:
        qry = """
            select	a.pk
                    , a.gubun
                    , c.code_nm as gubun_nm
                    , a.status
                    , b.code_nm as status_nm
                    , a.name
                    , a.description
                    , a.execution_script as executionscript
                    , a.param1
                    , a.param2
                    , a.param3
                    , a.status
                    , b.code_nm as status_nm
                    , a.use_yb
                    , to_char(a.create_date,'YYYY-MM-DD HH24:MI:SS') as create_date
                    , a.create_name
            from	job.job_templates a 
            inner join public.commcode b 
            on 		a.gubun  = b.code_id 
            inner join public.commcode c
            on 		a.status  = c.code_id 
            where 	b.cl_code = 11
            and 	c.cl_code = 12
            and		a.use_yb = '1'
            and		a.pk = %s
			"""
        pdb.execute_bind(qry , (jt_pk,))
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    result1 = {}
    for i, data in enumerate(pdatas, start=1):
        zipped_data = zip(pfields, data)
        result1 = {field: value for field, value in zipped_data}
        print(result1)
    print(f"status:",result1['status'])

    #상태가 비활성화이면 다시 활성화 불가, 관리자는 가능
    result1['authSave'] = True
    if result1['status']=='2':
        result1['authSave'] = False

    operatorid =''
    try:
        qry = """
            select	code_id
            from	public.commcode
            where	cl_code='10'
            and		code_id = %s
            and		use_yb ='1'
        """
        pdb.execute_bind(qry, (sawon_cd,))
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    if len(pdatas)>0:
        operatorid = str(pdatas[0][0])
    
    result1['authDel'] = False
    if operatorid==sawon_cd:
        result1['authSave'] = True
        result1['authDel'] = True

    return result1

@router.post("/jobTemplates", name="배치관리 작업목록 접수", description="", status_code=201)
def create_jobTemplates(
	request:CreateJobTempleate,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
	
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")
    
    sawon_nm = getSawonName(sawon_cd)
    print(f"sawon_nm{sawon_nm}")
    db = DbLink()
    pdb = PostgreLink()

    try:
        qry = "select nextval('job.seq_job_templates') as jt_pk"
        pdb.execute(qry)
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        db.close()
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    jt_pk = pdatas[0][0]
    print(f"jt_pk{jt_pk}")
    try:
        qry ="""
            insert into job.job_templates 
            (
                pk
                , name
                , gubun
                , status
                , description
                , execution_script
                , use_yb
                , create_date
                , create_by
                , create_name
                , update_date
                , update_by
                , update_name
            ) 
            values
            (
                %s
                , %s
                , %s
                , '1'
                , %s
                , %s
                , '1'
                , current_timestamp
                , %s
                , %s
                , current_timestamp
                , %s
                , %s
            )
			"""
        params = []
        params.extend([
            jt_pk
            , request.name
            , request.gubun
            , request.description
            , request.executionscript
            , sawon_cd
            , sawon_nm
            , sawon_cd
            , sawon_nm
            ])
        pdb.execute_bind(qry , params)
        pdb.commit()
    except PsycopgError as e:
        print(e)
        pdb.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    try:
        qry = """
            insert into job_templates
            values
            (
            :pk
            , :name
            , '1'
            )
        """
        bind_arr = {"pk":jt_pk, "name":request.name}
        db.execute(qry,bind_arr)
        db.commit()
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
		
    pdb.close()
    db.close()


@router.patch("/jobTemplates/{jt_pk}", name="배치관리 작업목록 업데이트", description="", status_code=200)
def update_jobTemplates(
	jt_pk:int,
    request:UpdateJobTempleate,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")

    sawon_nm = getSawonName(sawon_cd)

    db = DbLink()
    pdb = PostgreLink()

    try:
        qry ="""
            update	job.job_templates
            set		name = %s
                    , gubun = %s
                    , description = %s
                    , execution_script = %s
                    , status = %s
                    , param1 = %s
                    , param2 = %s
                    , param3 = %s
                    , update_date = current_timestamp
                    , update_by = %s
                    , update_name = %s
            where	pk = %s
            """
        params = []
        params.extend([
            request.name
            , request.gubun
            , request.description
            , request.executionscript
            , request.status
            , request.param1
            , request.param2
            , request.param3
            , sawon_cd
            , sawon_nm
            , jt_pk
            ])
        pdb.execute_bind(qry , params)
        pdb.commit()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

    try:
        qry ="""
            update  job_templates
            set     name = :name
            where   pk = :pk
            """
        bind_arr = {"name":request.name, "pk":jt_pk}
        db.execute(qry , bind_arr)
        db.commit()
    except PsycopgError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

    db.close()
    pdb.close()

@router.delete("/jobTemplates/{jt_pk}", name="배치관리 작업목록 삭제", description="", status_code=204)
def delete_jobTemplates(
	jt_pk: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")

    db = DbLink()
    pdb = PostgreLink()
    try:
        qry ="""
            update	job.job_templates
            set		use_yb = %s
                    , update_date = current_timestamp
                    , update_by = %s
            where	pk= %s
			"""
        pdb.execute_bind(qry , ("2", sawon_cd, jt_pk,))
        pdb.commit()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    
    try:
        qry ="""
            update  job_templates
            set     use_yb = '2'
            where   pk = :pk
            """
        bind_arr = {"pk":jt_pk}
        db.execute(qry , bind_arr)
        db.commit()
    except PsycopgError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

    db.close()
    pdb.close()

###############################

@router.get("/jobRequest", name="배치관리 작업요청 조회", description="", status_code=200)
def getlist_jobRequest(
    gubun: str = Query(...,description="gubun=0은 선택안함, gubun=1은 수수료, gubun=2는 일반", enum=[0,1,2]),
	jt_name: str = Query(None,description="작업목록 이름으로 검색"),
    jr_name: str = Query(None,description="작업요청 이름으로 검색"),
	page: int = Query(1,description="선택 페이지"),
	limit: int = Query(10,description="화면에 보여줄 갯수"),
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:dict = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")

    pdb = PostgreLink()
    list_field =[]
    pdatas=[]
    params=[]
    try:
        qry = f"""
                select 	a.pk as id
                        , a.create_by
                        , a.create_name
                        , b.gubun
                        , d.code_nm as gubun_nm
                        , b.name as jt_name
                        , a.name as jr_name
                        , a.status
                        , c.code_nm as status_nm
                        , to_char(a.create_date,'YYYY-MM-DD HH24:MI:SS') as create_date
                        , to_char(a.start_date,'YYYY-MM-DD HH24:MI:SS') as start_date
                        , to_char(a.end_date,'YYYY-MM-DD HH24:MI:SS') as end_date
                from 	job.job_request a
                inner join job.job_templates b
                on		a.jt_pk = b.pk
                inner join public.commcode c
                on		a.status = c.code_id
                inner join public.commcode d
                on		b.gubun = d.code_id
                where 	a.use_yb ='1'
                and		c.cl_code = 13
                and		d.cl_code = 12
			"""
        if gubun!="" and gubun != "0":
            qry += " and a.gubun = %s "
            params.append(gubun)
        if jt_name:
            qry += " and b.name like %s "
            jt_name = "%"+jt_name+"%"
            params.append(jt_name)
        if jr_name:
            qry += " and a.name like %s "
            jr_name = "%"+jr_name+"%"
            params.append(jr_name)

        qry += " order by a.pk desc limit %s offset (%s - 1) * %s"
        params.extend([limit, page, limit])
			
        pdb.execute_bind(qry , params)
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

    results = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
    pdb.close()

    return results
	
@router.get("/jobRequest/{jr_pk}", name="배치관리 작업요청 상세화면", description="", status_code=200)
def getdetail_jobRequest(
	jr_pk: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")
    pdb = PostgreLink()
    pdatas=[]
    list_field1 =[]
    list_field2 =[]
    try:
        qry = """
                select 	a.pk
                        , a.create_by
                        , a.create_name
                        , b.gubun
                        , d.code_nm as gubun_nm
                        , b.name as templates_name
                        , a.name as request_name
                        , a.status
                        , c.code_nm as status_nm
                        , to_char(a.create_date,'YYYY-MM-DD HH24:MI:SS') as create_date
                        , to_char(a.start_date,'YYYY-MM-DD HH24:MI:SS') as start_date
                        , to_char(a.end_date,'YYYY-MM-DD HH24:MI:SS') as end_date
                        , a.log
                from 	job.job_request a
                inner join job.job_templates b
                on		a.jt_pk = b.pk
                inner join public.commcode c
                on		a.status = c.code_id
                inner join public.commcode d
                on		b.gubun = d.code_id
                where 	a.use_yb ='1'
                and		c.cl_code = 13
                and		d.cl_code = 12
                and		a.pk = %s
			"""
        pdb.execute_bind(qry , (jr_pk,))
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    result1 = {}
    for i, data in enumerate(pdatas, start=1):
        zipped_data = zip(pfields, data)
        result1 = {field: value for field, value in zipped_data}
        print(result1)
    print(f"status:",result1['status'])

    #상태가 비활성화이면 다시 활성화 불가, 관리자는 가능
    result1['authDel'] = False
    result1['authSave'] = False
    if result1['status']=='1' and result1['create_by']==sawon_cd:
        result1['authDel'] = True
        result1['authSave'] = True

    operatorid =''
    try:
        qry = """
            select	code_id
            from	public.commcode
            where	cl_code='10'
            and		code_id = %s
            and		use_yb ='1'
        """
        pdb.execute_bind(qry, (sawon_cd,))
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    if len(pdatas)>0:
        operatorid = str(pdatas[0][0])
    
    if result1['status']=='1' and operatorid==sawon_cd:
        result1['authDel'] = True

    return result1

@router.post("/jobRequest", name="배치관리 작업요청 접수", description="", status_code=201)
def create_jobRequest(
	request:CreateJobRequest,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
	
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")
    
    sawon_nm = getSawonName(sawon_cd)

    db = DbLink()
    pdb = PostgreLink()

    # 작업목록에서 스크립트 가져옴
    try:
        qry = """
            select 	name
                    , execution_script 
            from 	job.job_templates
            where 	pk = %s
        """
        pdb.execute_bind(qry, (request.jt_pk,))
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    name, execution_script = pdatas[0]

    # 정보처리요청게시판에 접수
    try:
        qry = """
            select  to_char(sysdate,'yyyymmdd')||lpad(count(*) + 1, 3,0) jubsu_no
            from    info_request
            where   to_char(create_date, 'yyyymmdd') = to_char(sysdate, 'yyyymmdd')
        """
        db.execute(qry , {})
        datas = db.get_datas()
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    jubsu_no = datas[0][0]

    try:
        qry = """
            select seq_info_request.nextval new_pk from dual
        """
        db.execute(qry , {})
        datas = db.get_datas()
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    info_request_pk = int(''.join(map(str,datas[0])))

    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y%m%d")

    try:
        qry="""
        select dept_cd from sawon where sawon_cd = :sawon_cd
        """
        db.execute(qry , {"sawon_cd":sawon_cd})
        datas = db.get_datas()
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    request_dept_cd = datas[0][0]

    try:
        qry="""
            select  damdang_cd as damdang_dept_cd
                    , damdangja_cd as damdang_sawon_cd
                    , admin_damdangja as dev_sawon_cd
            from    develope_request a
                    , develope_request_admin b
            where   a.use_yb = '1'
            and     a.pk = 379
            and     a.pk = b.arc_pk
        """
        db.execute(qry , {})
        datas = db.get_datas()
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    damdang_dept_cd, damdang_sawon_cd, dev_sawon_cd = datas[0]
    print(f"info_request_pk{info_request_pk},jubsu_no{jubsu_no},formatted_time{formatted_time},request_dept_cd{request_dept_cd}")
    print(f"sawon_cd{sawon_cd},damdang_dept_cd{damdang_dept_cd},damdang_sawon_cd{damdang_sawon_cd},dev_sawon_cd{dev_sawon_cd}")
    print(f"name{name},execution_script{execution_script}")
    try:
        qry ="""
            insert  into info_request
            (
                pk
                ,jubsu_no
                ,menu_pk
                ,status_cd
                ,pre_finish
                ,request_dept_cd
                ,request_sawon_cd
                ,damdang_dept_cd
                ,damdang_sawon_cd
                ,dev_sawon_cd
                ,title
                ,content
                ,use_yb
                ,create_date
                ,create_by
                ,update_date
                ,confirm_damdang_yb
            )
            values
            (
                :new_pk
                ,:jubsu_no
                ,'379'
                ,'2'
                ,to_date(:pre_finish, 'yyyymmdd')
                ,:request_dept_cd
                ,:request_sawon_cd
                ,:damdang_dept_cd
                ,:damdang_sawon_cd
                ,:dev_sawon_cd
                ,:title
                ,:content
                ,'1'
                ,sysdate
                ,:create_by
                ,sysdate
                ,'1'
                )
            """
        bind_arr = {
                    "new_pk":info_request_pk
                    , "jubsu_no":jubsu_no
                    , "pre_finish":formatted_time
                    , "request_dept_cd":request_dept_cd
                    , "request_sawon_cd":sawon_cd
                    , "damdang_dept_cd":damdang_dept_cd
                    , "damdang_sawon_cd":damdang_sawon_cd
                    , "dev_sawon_cd":dev_sawon_cd
                    , "title":name
                    , "content":execution_script
                    , "create_by":sawon_cd
                    }
        db.execute(qry , bind_arr)
        db.commit()
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
    
    db.close()
    # 작업요청 이름 = 작업목록 이름 + 접수번호
    jr_name = name+'_'+jubsu_no
    
    # 작업요청 테이블 입력
    try:
        qry ="""
            insert into job.job_request 
            (
                pk
                , jt_pk
                , name
                , status
                , use_yb
                , create_date
                , create_by
                , create_name
            ) 
            values
            (
                nextval('job.seq_job_request')
                , %s
                , %s
                , '1'
                , '1'
                , current_timestamp
                , %s
                , %s
            )
			"""
        params = []
        params.extend([
            request.jt_pk
            , jr_name
            , sawon_cd
            , sawon_nm
            ])
        pdb.execute_bind(qry , params)
        pdb.commit()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    
    pdb.close()
    # jenkins 에 job 등록
    statusCode = createjob(execution_script , jr_name)

    if statusCode!= 200:
        raise HTTPException(status_code=404, detail="CreateJob Failed")
    


@router.patch("/jobRequest/{jr_pk}", name="배치관리 작업요청 업데이트", description="", status_code=200)
def update_jobRequest(
	jr_pk:int,
    request:UpdateJobTempleate,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")

    sawon_nm = getSawonName(sawon_cd)

    pdb = PostgreLink()

    try:
        qry ="""
            update	job.job_request
            set		start_date = %s
                    , end_date = %s
                    , log = %s
                    , status = %s
            where	pk = %s
            """
        params = []
        params.extend([
            request.start_date
            , request.end_date
            , request.log
            , request.status
            , jr_pk
            ])
        pdb.execute_bind(qry , params)
        pdb.commit()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

    pdb.close()    

@router.delete("/jobRequest/{jr_pk}", name="배치관리 작업요청 삭제", description="", status_code=204)
def delete_jobRequest(
	jr_pk: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")
    pdb = PostgreLink()
    try:
        qry ="""
            update	job.job_request
            set		use_yb = '2'
            where	pk= %s
			"""
        pdb.execute_bind(qry , (jr_pk,))
        pdb.commit()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    pdb.close()

def jenkinsBuildNum(jenkins_url, job_name, jenkins_user, jenkins_token):
    api_url = f"{jenkins_url}/job/{job_name}/api/json"
    response = requests.post(
        api_url,
        auth=(jenkins_user, jenkins_token)
    )

    # 응답 확인
    if response.status_code == 200:
        # API 응답에서 실행 번호 추출
        last_build_number = 9999
        build_info = response.json()
        print(f"build_info{build_info}")
        if build_info is not None:
            if build_info["lastBuild"] is not None:
                last_build_number = build_info["lastBuild"]["number"]
            
        #print(f"최신 빌드의 실행 번호: {build_number}")
        print(f"최신 빌드의 번호: {last_build_number}")
    else:
        print(f'API 호출 중 오류가 발생했습니다. 응답 코드: {response.status_code}, 내용: {response.text}')

    return last_build_number

@router.post("/jobRequest/{jr_pk}/execute", name="배치관리 작업요청 실행", description="", status_code=201)
def update_jobRequest(
	jr_pk:int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")

    sawon_nm = getSawonName(sawon_cd)

    pdb = PostgreLink()

    jenkins_url = 'http://10.16.16.180:8080/'
    jenkins_user = 'incar'
    jenkins_token = '114a6393430728c13b7d8e5bd7ad3a6080'
    jenkins_token = '11ae9647a7cb4a55f1392d92ea4a0d04dd'

    try:
        qry="""
            select 	name
            from 	job.job_request
            where 	pk = %s
        """
        pdb.execute_bind(qry , (jr_pk,))
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    job_name = pdatas[0][0]
    # job_name = 'NewJob3'  # 생성한 Job의 이름
    
    last_build_number = jenkinsBuildNum(jenkins_url, job_name, jenkins_user, jenkins_token)

    # Jenkins API URL 및 기본 헤더 설정
    api_url = f'{jenkins_url}/job/{job_name}/build'
    headers = {
        'Content-Type': 'application/xml',
    }

    # Job 실행 요청 보내기
    response = requests.post(
        api_url,
        auth=(jenkins_user, jenkins_token),
        headers=headers
    )

    # 응답 확인
    if response.status_code == 201:
        #print(f'Job "{job_name}"을 성공적으로 비동기적으로 실행했습니다.')
        #print(f"실행번호:{response.headers['Location']}")  # Job의 실행 번호 반환
        while True:
            new_build_number = jenkinsBuildNum(jenkins_url, job_name, jenkins_user, jenkins_token)
            
            if last_build_number ==new_build_number:
                print("신규 빌드 대기중")
                time.sleep(5)
            else:
                print(f"신규 빌드의 번호: {new_build_number}")
                try:
                    qry="""
                        update 	job.job_request
                        set 	build_number = %s
                                , status = '2'
                                , start_date = current_timestamp
                        where 	pk = %s
                    """
                    pdb.execute_bind(qry , (new_build_number, jr_pk,))
                    pdb.commit()
                    pdb.close()
                except PsycopgError as e:
                    pdb.close()
                    raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
                break
    else:
        print(f'Job 실행 중 오류가 발생했습니다. 응답 코드: {response.status_code}, 내용: {response.text}')

    pdb.close()

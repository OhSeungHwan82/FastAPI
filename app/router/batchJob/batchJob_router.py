# -*- coding: utf-8 -*-
from fastapi import APIRouter, Body, Query, Depends, HTTPException, File, UploadFile, Form, Request
from app.database.postgre import PostgreLink
from psycopg2 import Error as PsycopgError
from app.database.orcl import DbLink
from cx_Oracle import DatabaseError as OracleError
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from app.models.batchJobModels import CreateJobTempleate, UpdateJobTempleate, CreateJobRequest, ExecJobTempleate
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

def createjob(execution_script, job_name, buildschedule, parameters):
    jenkins_url = 'http://10.16.16.180:8080/'
    jenkins_user = 'incar'
    jenkins_token = '11ae9647a7cb4a55f1392d92ea4a0d04dd'
	
    api_url = f'{jenkins_url}/createItem'
    headers = {
        'Content-Type': 'application/xml',
    }
    print("buildschedule : "+buildschedule)
    # 스케줄 추가
    if buildschedule:
        add_buildschedule = f"""
        <triggers>
            <hudson.triggers.TimerTrigger>
                <spec>{buildschedule}</spec>
            </hudson.triggers.TimerTrigger>
        </triggers>
        """
    else:
        add_buildschedule=""
    # 파라미터 추가
    add_item = ''
    for i, item in enumerate(parameters, start=1):
        if item.name:
            add_item += f"""
            <hudson.model.StringParameterDefinition>
                <name>{item.name}</name>
                <description></description>
                <defaultValue></defaultValue>
                <trim>false</trim>
            </hudson.model.StringParameterDefinition>
            """
    print(f"add_item : {add_item}")
    if add_item:
        # <hudson.model.BooleanParameterDefinition>
        #     <name>PARAM2</name>
        #     <description>Second parameter</description>
        #     <defaultValue>true</defaultValue>
        # </hudson.model.BooleanParameterDefinition>
        add_parameter = f"""
        <properties>
            <hudson.model.ParametersDefinitionProperty>
                <parameterDefinitions>
                    {add_item}
                </parameterDefinitions>
            </hudson.model.ParametersDefinitionProperty>
        </properties>
        """
    else:
        add_parameter=""
    # 새로운 Job의 구성 XML 생성
    new_job_name = job_name
    # shell script 에서 & 입력은 &amp; 로 입력해야함 & 가 xml에서 예약문자라 & 를 데이터값으로 포함하려면 amp; 를 붙여야함
    # &gt; 는 > 를 인코딩
    new_job_xml = f"""
    <project>
    {add_parameter}
    <builders>
        <hudson.tasks.Shell>
        <command>{execution_script}</command>
        </hudson.tasks.Shell>
    </builders>
    {add_buildschedule}
    </project>
    
    """
    print("new_job_xml : "+new_job_xml)
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
    gubun: str = Query(...,description="gubun=1은 수수료, gubun=3는 Cron", enum=[1,3]),
    status: str = Query(...,description="status=0은 전체, status=1은 활성, status=2는 비활성", enum=[0,1,2]),
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
                    , b.code_nm as gubun_nm
                    , a.status
                    , c.code_nm as status_nm
                    , a.build_schedule
                    , a.use_yb
                    , to_char(a.update_date,'YYYY-MM-DD HH24:MI:SS') as update_date
                    , a.update_name
            from	job.job_templates a 
            inner join public.commcode b 
            on 		a.gubun  = b.code_id 
            inner join public.commcode c
            on 		a.status  = c.code_id 
            where 	b.cl_code = 12
            and 	c.cl_code = 11
            and		a.use_yb = '1'   
			"""
        if status != "0":
            qry += " and a.status = %s "
            params.append(status)
        if gubun!="":
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
                    , b.code_nm as gubun_nm
                    , a.status
                    , c.code_nm as status_nm
                    , a.name
                    , a.description
                    , a.execution_script as executionscript
                    , a.build_schedule as buildschedule
                    , a.param1
                    , a.param2
                    , a.param3
                    , a.use_yb
                    , to_char(a.create_date,'YYYY-MM-DD HH24:MI:SS') as create_date
                    , a.create_name
            from	job.job_templates a 
            inner join public.commcode b 
            on 		a.gubun  = b.code_id 
            inner join public.commcode c
            on 		a.status  = c.code_id 
            where 	b.cl_code = 12
            and 	c.cl_code = 11
            and		a.use_yb = '1'
            and		a.pk = %s
			"""
        pdb.execute_bind(qry , (jt_pk,))
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    result = {}
    for i, data in enumerate(pdatas, start=1):
        zipped_data = zip(pfields, data)
        result = {field: value for field, value in zipped_data}
        print(result) 
    print(f"status:",result['status'])
    result['params'] = [
        {"name":result['param1'], "value":""},
        {"name":result['param2'], "value":""}
    ]
    #상태가 비활성화이면 다시 활성화 불가, 관리자는 가능
    result['authSave'] = True
    result['authExec'] = True
    if result['status']=='2':
        result['authSave'] = False
        result['authExec'] = False
    # IIMS와 연동 안된상태라 관리자만 처리 가능하게 변경
    result['authSave'] = False
    operatorid =''
    try:
        qry = """
            select	code_id
            from	public.commcode
            where	cl_code in ('14','15')
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
    
    result['authDel'] = False
    if operatorid==sawon_cd:
        result['authSave'] = True
        result['authDel'] = True
    print(f"result : {result}")
    return result

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
    
    # print(f"itemlist : {request}")
    # param1 = ''
    # param2 = ''
    for i, item in enumerate(request.params, start=1):
        print(item.name)
        globals()[f"param{i}"] = item.name
    print(f"param1 : {param1}")
    print(f"param2 : {param2}")
    # return
    sawon_nm = getSawonName(sawon_cd)
    print(f"sawon_nm{sawon_nm}")
    db = DbLink()
    pdb = PostgreLink()

    try:
        qry = """
            select 	count(*) cnt
            from 	job.job_templates
            where 	name = %s   
                    """
        pdb.execute_bind(qry, (request.name,))
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        db.close()
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    chk_name = pdatas[0][0]

    if chk_name>0:
        raise HTTPException(status_code=422, detail="동일한 이름의 작업목록이 있습니다.")

    try:
        qry = "select nextval('job.seq_job_templates') as jt_pk"
        pdb.execute(qry)
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        db.close()
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    jt_pk = pdatas[0][0]

    try:
        qry ="""
            insert into job.job_templates 
            (
                pk
                , name
                , gubun
                , status
                , execution_script
                , build_schedule
                , description
                , use_yb
                , create_date
                , create_by
                , create_name
                , update_date
                , update_by
                , update_name
                , param1
                , param2
            ) 
            values
            (
                %s
                , %s
                , %s
                , %s
                , %s
                , %s
                , %s
                , '1'
                , current_timestamp
                , %s
                , %s
                , current_timestamp
                , %s
                , %s
                , %s
                , %s
            )
			"""
        params = []
        if request.executionscript is None:
            request.executionscript =''
        if request.buildschedule is None:
            request.buildschedule =''
        if request.description is None:
            request.description =''
        params.extend([
            jt_pk
            , request.name
            , request.gubun
            , request.status
            , request.executionscript
            , request.buildschedule
            , request.description
            , sawon_cd
            , sawon_nm
            , sawon_cd
            , sawon_nm
            , param1
            , param2
            ])
        print(params)
        pdb.execute_bind(qry , params)
        pdb.commit()
    except PsycopgError as e:
        print(e)
        pdb.close()
        raise HTTPException(status_code=500, detail=f"Postgresql Database error: {e}")

    try:
        qry = """
            insert into job_templates
            values
            (
            :pk
            , :name
            , :gubun
            , :status
            , '1'
            )
        """
        bind_arr = {"pk":jt_pk, "name":request.name, "gubun":request.gubun, "status":request.status}
        db.execute(qry,bind_arr)
        db.commit()
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

    if request.gubun=='3':
        jr_name = "cron_"+request.name
    else:
        jr_name = "susuryo_"+request.name
    statusCode = createjob(request.executionscript , jr_name, request.buildschedule, request.params)

    if statusCode!= 200:
        raise HTTPException(status_code=404, detail="CreateJob Failed")
		
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
    try:
        qry = f"""
                update  job_templates
                set     status={request.status}
                where   pk=:pk        
        """
        bind_arr = {"pk":jt_pk}

        db.execute(qry , bind_arr)
        db.commit()
        # fields = db.get_field_names()
        # datas = db.get_datas()
        # print(datas)
        # sawon_nm = datas[0][0]
        db.close()
    except OracleError as e:
        print("예외발생1",e)
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

    # db.close()
    # db = DbLink()

    # try:
    #     qry ="""
    #             update  job_templates
    #             set     status = :status
    #             where   pk = :pk
    #         """
    #     bind_arr = {"status":request.status, "pk":jt_pk}
    #     db.execute(qry , bind_arr)
    #     # db.commit()
    # except OracleError as e:
    #     db.close()
    #     raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

    pdb = PostgreLink()

    try:
        qry ="""
            update	job.job_templates
            set		description = %s
                    , status = %s
                    , update_date = current_timestamp
                    , update_by = %s
                    , update_name = %s
            where	pk = %s
            """
        params = []
        params.extend([
            request.description
            , request.status
            , sawon_cd
            , sawon_nm
            , jt_pk
            ])
        pdb.execute_bind(qry , params)
        pdb.commit()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

    if request.status=='2':
        try:
            qry = """
                select 	name
                        , gubun
                from 	job.job_templates
                where   pk = %s
            """
            pdb.execute_bind(qry, (jt_pk,))
            pfields = pdb.get_field_names()
            pdatas = pdb.get_datas()
        except PsycopgError as e:
            pdb.close()
            raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
        if len(pdatas)>0:
            job_name = str(pdatas[0][0])
            job_gubun = str(pdatas[0][1])
        print(f"job_name:{job_name}")
        print(f"job_gubun:{job_gubun}")
        if job_gubun=='3':
            job_name = "cron_"+job_name
        elif job_gubun=='1':
            job_name = "susuryo_"+job_name
        jenkins_url = 'http://10.16.16.180:8080/'
        jenkins_user = 'incar'
        jenkins_token = '11ae9647a7cb4a55f1392d92ea4a0d04dd'
        api_url = f'{jenkins_url}/job/{job_name}/disable'
        # Jenkins API 호출에 필요한 헤더 설정
        headers = {
            'Content-Type': 'application/xml',
        }
        response = requests.post(
            api_url,
            auth=(jenkins_user, jenkins_token),
            headers=headers
        )
        # 응답 코드 확인
        if response.status_code == 200:
            print(f'Job이 성공적으로 비활성화되었습니다.')
        else:
            print(f'Job 비활성화 실패. 응답 코드: {response.status_code}, 응답 내용: {response.text}')
    
    
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
    except OracleError as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

    db.close()
    pdb.close()

@router.post("/jobTemplates/{jt_pk}/execute", name="배치관리 작업목록 실행", description="", status_code=201)
def update_jobRequest(
	jt_pk:int,
    request:ExecJobTempleate,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    if not sawon_cd:
        raise HTTPException(status_code=404, detail="User Not Found")

    sawon_nm = getSawonName(sawon_cd)

    jenkins_url = 'http://10.16.16.180:8080/'
    jenkins_user = 'incar'
    jenkins_token = '11ae9647a7cb4a55f1392d92ea4a0d04dd'

    pdb = PostgreLink()
    # 실행시키기 위한 Job 이름 획득
    try:
        qry="""
            select 	pk
                    , name
                    , gubun
            from 	job.job_templates a
            where 	a.use_yb ='1'
            and     a.pk=%s
        """
        pdb.execute_bind(qry , (jt_pk,))
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    jt_pk = pdatas[0][0]
    job_name = pdatas[0][1]
    job_gubun = pdatas[0][2]
    if job_gubun=='1':
        job_name = "susuryo_"+job_name
    else:
        job_name = "cron_"+job_name
    print("여기까지:")
    last_build_number = jenkinsBuildNum(jenkins_url, job_name, jenkins_user, jenkins_token)
    print("last_build_number:",last_build_number)
    # Jenkins API URL 및 기본 헤더 설정
    params = {}
    # for i, item in enumerate(request.params, start=1):
    #      params[item.name] = item.value
    # print(f"params : {params}")
    
    for i, item in enumerate(request.params, start=1):
        if item.value:
            print(item.value)
            params[item.name] = item.value
    print(f"params: {params}")
    # return
    if params:
        api_url = f'{jenkins_url}/job/{job_name}/buildWithParameters'
        print(f"api_url : {api_url}")
        headers = {
            'Content-Type': 'application/xml',
        }
        # Job 실행 요청 보내기
        response = requests.post(
            api_url,
            auth=(jenkins_user, jenkins_token),
            params=params,
            headers=headers
        )
    else:
        api_url = f'{jenkins_url}/job/{job_name}/build'
        print(f"api_url : {api_url}")
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
                    qry = """
                            select code_id
                            from public.commcode
                            where cl_code='9'
                            and use_yb ='1'
                    """
                    pdb.execute(qry)
                    pfields = pdb.get_field_names()
                    pdatas = pdb.get_datas()
                except PsycopgError as e:
                    pdb.close()
                    raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
                systemid = pdatas[0][0]
                try:
                    qry = "select nextval('job.seq_job_request') as jr_pk"
                    pdb.execute(qry)
                    pdatas = pdb.get_datas()
                except PsycopgError as e:
                    pdb.close()
                    raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
                jr_pk = pdatas[0][0]
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
                            , build_number
                            , start_date
                        ) 
                        values
                        (
                            %s
                            , %s
                            , %s
                            , '2'
                            , '1'
                            , current_timestamp
                            , %s
                            , %s
                            , %s
                            , current_timestamp
                        )
                        """
                    bind = []
                    bind.extend([
                        jr_pk
                        , jt_pk
                        , job_name
                        , systemid
                        , '서비스'
                        , new_build_number
                        ])
                    pdb.execute_bind(qry , bind)
                    pdb.commit()
                except PsycopgError as e:
                    pdb.close()
                    raise HTTPException(status_code=500, detail=f"Database error: {e}")
                
                for key, value in params.items():
                    print(f"key:{key}, value:{value}")
                    try:
                        qry ="""
                            insert into job.job_request_parameters 
                            (
                                pk
                                , jr_pk
                                , name
                                , type
                                , value
                                , use_yb
                                , create_date
                                , create_by
                            ) 
                            values
                            (
                                nextval('job.seq_job_request_parameters')
                                , %s
                                , %s
                                , 'string'
                                , %s
                                , '1'
                                , current_timestamp
                                , %s
                            )
                            """
                        bind = []
                        bind.extend([
                            jr_pk
                            , key
                            , value
                            , systemid
                            ])
                        pdb.execute_bind(qry , bind)
                        pdb.commit()
                    except PsycopgError as e:
                        pdb.close()
                        raise HTTPException(status_code=500, detail=f"Database error: {e}")
                
                break
    else:
        print(f'Job 실행 중 오류가 발생했습니다. 응답 코드: {response.status_code}, 내용: {response.text}')

    pdb.close()    

###############################

@router.get("/jobRequest", name="배치관리 작업요청 조회", description="", status_code=200)
def getlist_jobRequest(
    gubun: str = Query(...,description="gubun=0은 선택안함, gubun=1은 수수료, gubun=2는 일반", enum=[0,1,2]),
	jt_name: str = Query(None,description="작업목록 이름으로 검색"),
    jr_name: str = Query(None,description="작업요청 이름으로 검색"),
    jr_startdate: str = Query(None,description="작업요청 시작일로 검색"),
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
            qry += " and b.gubun = %s "
            params.append(gubun)
        if jt_name:
            qry += " and b.name like %s "
            jt_name = "%"+jt_name+"%"
            params.append(jt_name)
        if jr_name:
            qry += " and a.name like %s "
            jr_name = "%"+jr_name+"%"
            params.append(jr_name)
        if jr_startdate:
            qry += " and a.start_date between to_date(%s,'yyyymmdd')  and  to_date(%s,'yyyymmdd')+interval '1 month' - interval '1 day'"
            jr_startdate = jr_startdate+'01'
            params.append(jr_startdate)
            params.append(jr_startdate)

        qry += " order by a.pk desc limit %s offset (%s - 1) * %s"
        params.extend([limit, page, limit])
        print(f"qry:",qry)
			
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
    result = {}
    for i, data in enumerate(pdatas, start=1):
        zipped_data = zip(pfields, data)
        result = {field: value for field, value in zipped_data}
        print(result)
    
    print(f"status:",result['status'])

    try:
        qry = """
        select 	name
                , value
        from 	job.job_request_parameters
        where 	jr_pk = %s
			"""
        pdb.execute_bind(qry , (jr_pk,))
        pfields = pdb.get_field_names()
        pdatas = pdb.get_datas()
    except PsycopgError as e:
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    # for i, data in enumerate(pdatas, start=1):
    #     zipped_data = zip(pfields, data)
    #     param_result = {field: value for field, value in zipped_data}
    # results = {"params":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
    # print(f"pdatas : {pdatas}")
    # print(f"param_result : {param_result}")
    result['params'] = [{field:value for field, value in zip(pfields, data)} for data in pdatas]
    # result['params'] = [
    #     {"name":result['param1'], "value":""},
    #     {"name":result['param2'], "value":""}
    # ]

    #상태가 비활성화이면 다시 활성화 불가, 관리자는 가능
    result['authDel'] = False
    result['authSave'] = False
    # if result1['status']=='1' and result1['create_by']==sawon_cd:
    #     result1['authDel'] = True
    #     result1['authSave'] = True

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
    
    if result['status']=='1' and operatorid==sawon_cd:
        result['authDel'] = True
        result['authSave'] = True
    # IIMS와 연동 안된상태라 작업목록에서 실행 처리
    result['authSave'] = False
    print(f"result : {result}")
    return result

@router.post("/jobRequest", name="배치관리 작업요청 접수", description="", status_code=201)
def create_jobRequest(
	request:CreateJobRequest,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
	
):
    code:str = user_service.decode_jwt(access_token=access_token)
    sawon_cd:str|None = user_service.get_regist_info(code=code)
    # test
    # sawon_cd = '1611006'
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
            and     a.pk = 390
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
                ,'390'
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
        print(e)
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
        print(e)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    
    pdb.close()
    # jenkins 에 job 등록
    statusCode = createjob(execution_script , jr_name, '')
    print(statusCode)
    if statusCode!= 200:
        raise HTTPException(status_code=404, detail="CreateJob Failed")
    


# @router.patch("/jobRequest/{jr_pk}", name="배치관리 작업요청 업데이트", description="", status_code=200)
# def update_jobRequest(
# 	jr_pk:int,
#     request:UpdateJobTempleate,
# 	access_token:str=Depends(sc.get_access_token),
# 	user_service:UserService=Depends(UserService),
# ):
#     code:str = user_service.decode_jwt(access_token=access_token)
#     sawon_cd:str|None = user_service.get_regist_info(code=code)
#     if not sawon_cd:
#         raise HTTPException(status_code=404, detail="User Not Found")

#     sawon_nm = getSawonName(sawon_cd)

#     pdb = PostgreLink()

#     try:
#         qry ="""
#             update	job.job_request
#             set		start_date = %s
#                     , end_date = %s
#                     , log = %s
#                     , status = %s
#             where	pk = %s
#             """
#         params = []
#         params.extend([
#             request.start_date
#             , request.end_date
#             , request.log
#             , request.status
#             , jr_pk
#             ])
#         pdb.execute_bind(qry , params)
#         pdb.commit()
#     except PsycopgError as e:
#         pdb.close()
#         raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

#     pdb.close()    

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
    last_build_number = 9999
    if response.status_code == 200:
        # API 응답에서 실행 번호 추출
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

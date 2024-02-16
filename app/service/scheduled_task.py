from app.database.postgre import PostgreLink
from psycopg2 import Error as PsycopgError
from app.database.orcl import DbLink
from cx_Oracle import DatabaseError as OracleError
import requests
from fastapi import APIRouter, Body, Query, Depends, HTTPException

def scheduled_task():
    #오라클 접속 정보처리요청게시판에 상태 진행건이 포스트그레에 있는지 체크하고 없으면 입력
    url = "http://127.0.0.1:8000/api/ledgerDatabase/jubsu?gubun=0&page=1&limit=10"

    db = DbLink()
    try:
        qry = """
                select pk
                     , jubsu_no
                     , title
                  from info_request
                 where menu_pk=160
                   and use_yb ='1'
                   and create_date>to_date('20231129','yyyymmdd')
                   and status_cd ='5'
				"""

        db.execute(qry , {})
		
        fields = db.get_field_names()
        datas = db.get_datas()
        print("datas",datas)
    except OracleError as e:
        print("예외발생",e)
        db.close()
        raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

    pdb = PostgreLink()
    jubsu_chk = 0
    try:
        qry = """
				select 		info_request_pk
				from 		ledger.ledger_database 
				where 		use_yb = '1'
				"""
        pdb.execute(qry)
        pdatas = pdb.get_datas()
        print("pdatas",pdatas)
    except PsycopgError as e:
        db.close()
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

    pdatas_set = set(item[0] for item in pdatas)

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
        db.close()
        pdb.close()
        raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
    systemid = pdatas[0][0]

    # datas에만 있는 값을 추출하여 새로운 리스트 생성
    list_difference = []
    for item in datas:
        if item[0] not in pdatas_set:
            list_difference.append(item)
            try:
                qry = """
                        select count(*) cnt 
                          from ledger.ledger_database
                         where info_request_pk = %s
                    """
                pdb.execute_bind(qry,(item[0],))
                pfields = pdb.get_field_names()
                pdatas = pdb.get_datas()
                ld_cnt = pdatas[0][0]
            except PsycopgError as e:
                db.close()
                pdb.close()
                raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
            if ld_cnt==0:
                try:
                    qry ="""
                        insert into 	ledger.ledger_database 
                                        (
                                                pk
                                            , 	info_request_pk
                                            , 	jubsu_no
                                            , 	title
                                            , 	request_sql
                                            , 	response_sql
                                            , 	status_cd
                                            , 	backup_file
                                            , 	use_yb
                                            , 	create_date
                                            , 	create_by
                                            , 	update_date
                                            ,	update_by
                                        ) 
                        values
                                        (
                                                nextval('ledger.seq_ledger_database')
                                            , 	%s
                                            , 	%s
                                            , 	%s
                                            , 	''
                                            , 	''
                                            , 	'1'
                                            , 	''
                                            , 	'1'
                                            , 	current_timestamp
                                            , 	%s
                                            , 	current_timestamp
                                            , 	%s
                                        )
                        """
                    pdb.execute_bind(qry , (item[0], item[1], item[2], systemid, systemid,))
                    pdb.commit()
                except PsycopgError as e:
                    pdb.close()
                    db.close()
                    raise HTTPException(status_code=500, detail=f"Database error: {e}")
		
    pdb.close()
    db.close()
    
def batchJob_scheduled_task():
    print("배치관리 스케줄 시작")
    jenkins_url = 'http://10.16.16.180:8080/'
    jenkins_user = 'incar'
    jenkins_token = '11ae9647a7cb4a55f1392d92ea4a0d04dd'

    # 작업중인 job 에 대한 모니터링
    pdb = PostgreLink()
    qry="""
        select 	pk 
                , name 
                , build_number
        from 	job.job_request
        where 	use_yb ='1'
        and 	status = '2'
    """
    pdb.execute(qry)
    pfields = pdb.get_field_names()
    pdatas = pdb.get_datas()
    for item in pdatas:
        jr_pk = item[0]
        job_name = item[1]
        build_number = item[2]

        api_url = f'{jenkins_url}/job/{job_name}/{build_number}/api/json'
        headers = {
            'Content-Type': 'application/xml',
        }
        response = requests.get(
            api_url,
            auth=(jenkins_user, jenkins_token),
            headers=headers
        )
        if response.status_code == 200:
            job_status = response.json()
            if job_status['building']:
                print(f'Job이 실행 중입니다. (빌드 번호: {job_status["number"]})')
            else:
                print(f'Job이 완료되었습니다. (빌드 번호: {job_status["number"]}, 결과: {job_status["result"]})')
                try:
                    qry="""
                        update 	job.job_request
                        set 	status = '3'
                                , end_date = current_timestamp
                        where 	pk = %s
                    """
                    pdb.execute_bind(qry , (jr_pk,))
                except PsycopgError as e:
                    pdb.close()
                    raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
        
        api_url = f'{jenkins_url}/job/{job_name}/{build_number}/consoleText'
        headers = {
            'Content-Type': 'text/plain',
        }

        response = requests.get(
            api_url,
            auth=(jenkins_user, jenkins_token),
            headers=headers
        )

        if response.status_code == 200:
            console_output = response.text
            print(f"console_output{console_output}")
            try:
                qry="""
                    update 	job.job_request
                    set 	log = %s
                    where 	pk = %s
                """
                pdb.execute_bind(qry , (console_output, jr_pk,))
            except PsycopgError as e:
                pdb.close()
                raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
        else:
            print(f'Console Output을 가져오는 중 오류가 발생했습니다. 응답 코드: {response.status_code}, 내용: {response.text}')
    pdb.commit()
    pdb.close()
    print("배치관리 스케줄 종료")
    # 상태가 진행중인 건에 대해서 스케줄러에서 5분마다 체크
    # 상태가 완료 되면 모니터링 제외
    # 작업요청 테이블에 상태 변경

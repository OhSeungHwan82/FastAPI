# -*- coding: utf-8 -*-
from fastapi import APIRouter, Body, Query, Depends, HTTPException, File, UploadFile, Form
from app.database.postgre import PostgreLink
from psycopg2 import Error as PsycopgError
from app.database.orcl import DbLink
from cx_Oracle import DatabaseError as OracleError
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from app.models.ledgerDatabaseModels import CreateRequest, UpdateRequest, CreateReviveRequest
from app.service.user import UserService
from app.routers.userInfo import security as sc
from app.config.settings import root_dir

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
    prefix="/api/ledgerDatabase",
)
#생성SQL 파일생성
def create_execfiles(ld_pk):
	current_time = datetime.now()
	formatted_time = current_time.strftime("%Y%m%d%H%M%S")
	file_name = str(ld_pk)+"_"+formatted_time+".json"
	pdb = PostgreLink()
	try:
		qry ="""
				select 		a.column_value as "변경컬럼"
						, 	a.before_value as "변경전"
						, 	a.after_value as "변경후"
						, 	a.forecast_sql as "예상SQL"
						, 	b.code_nm as "생성결과"
						,	c.code_nm as "실행결과"
				from 		ledger.ledger_database_exec_sql a
							inner join public.commcode b on b.cl_code = '3' and b.code_id = a.status_cd
							inner join public.commcode c on c.cl_code = '4' and c.code_id = a.result_cd
				where 		a.use_yb = %s
				and 		a.ld_pk = %s
				order by 	a.pk
		"""
		pdb.execute_bind(qry , ("1", ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	
	exec_file_name = "execFile_"+str(ld_pk)+"_"+formatted_time+".csv"
	exec_output_file_path = os.path.join('./files/execFiles', exec_file_name)
	with open(exec_output_file_path, 'w', encoding='utf-8') as f:
		writer = csv.writer(f, delimiter='\t')
		writer.writerow(pfields)
		for row in pdatas:
			writer.writerow(row)

	try:
		sql = """
		update  ledger.ledger_database 
		set     exec_file=%s 
		where   pk = %s
		"""
		pdb.execute_bind(sql,(exec_file_name, ld_pk,))
		# pdb.commit()
	except PsycopgError as e:
		pdb.close()
		print(f"PostgreSQL Database error: {e}")
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	pdb.commit()
	pdb.close()

# 20231110 s.j.b 수정
@router.get("/jubsu", name="원장변경 접수현황 목록조회", description="", status_code=200)
def getlist(
    gubun: str = Query(...,description="gubun=0은 선택안함, gubun=1은 접수번호, gubun=2는 접수제목", enum=[0,1,2]),# 선택안함: 0, 접수번호: 1, 접수제목: 2
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
				select 	a.pk as id
						, 	a.info_request_pk
						, 	a.jubsu_no
						, 	a.title
						, 	a.status_cd
						,	b.code_nm   as status_nm
						,	to_char(a.create_date,'YYYY-MM-DD HH24:MI:SS') as create_date
				from   	ledger.ledger_database    a
						inner join public.commcode   b on a.status_cd  = b.code_id and b.cl_code = 1
				where  a.use_yb = '1'
					"""
		if gubun :
			if gubun == "0" and search:
				qry += " and jubsu_no = %s or title like %s "
				params.append(search)
				search = "%"+search+"%"
				params.append(search)
			if gubun == "1" and search:
				qry += " and jubsu_no = %s "
				params.append(search)
			if gubun == "2" and search:
				qry += " and title like %s "
				search = "%"+search+"%"
				params.append(search)

		# if gubun != "0" and search:
		# 	if gubun == "1":
		# 		qry += " and jubsu_no = %s "
		# 	if gubun == "2":
		# 		qry += " and title like %s "
		# 		search = "%"+search+"%"
		# 	params.append(search)

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
	
# 20231110 s.j.b 수정	
@router.get("/jubsu/{ld_pk}", name="원장변경 접수현황 상세화면", description="", status_code=200)
def getdetail(
	ld_pk: int,# = Query(None,description="ledger_database의 pk")
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
			select 		a.pk
					, 	a.info_request_pk
					, 	a.jubsu_no
					, 	a.title
					, 	case when a.request_file is null or a.request_file ='' then a.request_sql else '' end request_sql
					, 	case when a.create_file is null or a.create_file ='' then a.response_sql else '' end response_sql
					, 	a.status_cd
					,	a.is_valid
					,   a.request_file
					,   a.create_file
					,   a.exec_file
					, 	(select count(*) cnt from ledger.ledger_database_exec_sql b where a.pk = b.ld_pk and b.use_yb ='1') totalcount
			from 		ledger.ledger_database a
			where 		a.use_yb = %s
			and 		pk = %s
			"""
		pdb.execute_bind(qry , ("1", ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	result = {}
	for i, data in enumerate(pdatas, start=1):
		result = {field:value for field, value in zip(pfields, data)}

	operatorid =''
	try:
		qry = """
                select code_id
                  from public.commcode
                 where cl_code='10'
				   and code_id = %s
                   and use_yb ='1'
		"""
		pdb.execute_bind(qry, (sawon_cd,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if len(pdatas)>0:
		operatorid = str(pdatas[0][0])

	#저장 authSave
	#SQL생성 authCreate
	#검토완료 authTest
	#실행 authExec
	result['authSave'] = False
	result['authCreate'] = False
	result['authConfirm'] = False
	result['authExec'] = False
	result['authDel'] = False
	if result['status_cd'] == '1' or result['status_cd']=='2' or result['status_cd']=='4': #접수, 진행, 실패일 경우에는 요청SQL 입력가능
		#저장버튼 활성화
		result['authSave'] = True
		if result['status_cd']=='2' or result['status_cd']=='4':
			if result['request_sql'] or result['request_file']:
				result['authCreate'] = True
			if result['response_sql'] or result['create_file']:
				result['authConfirm'] = True
	if result['status_cd']=='5' and operatorid==sawon_cd:
		result['authExec'] = True
	if operatorid==sawon_cd:
		result['authDel'] = True
	try:
		qry ="""
				select 		a.pk as id
						, 	a.ld_pk
						, 	a.column_value
						, 	a.before_value
						, 	a.after_value
						, 	a.forecast_sql
						,	a.status_cd
						, 	b.code_nm as status_nm
						,	a.result_cd
						,	c.code_nm as result_nm
				from 		ledger.ledger_database_exec_sql a
							inner join public.commcode b on b.cl_code = '3' and b.code_id = a.status_cd
							inner join public.commcode c on c.cl_code = '4' and c.code_id = a.result_cd
				where 		a.use_yb = %s
				and 		a.ld_pk = %s
				order by 	a.pk
		"""
		pdb.execute_bind(qry , ("1", ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	result['list'] = [{field:value for field, value in zip(pfields, data)} for data in pdatas]
	# print(f'pdatas : {pdatas}')
	# pdatas [(5677, 46, 'name_kor', '홍길동', "'홍길동1'"), (5678, 46, 'name_kor', '홍길동', "'홍길동2'"), (5679, 46, 'name_kor', '홍길동', "'홍길동3'")]
	# pfields : ['id', 'ld_pk', 'column_value', 'before_value']
	print(f'result : {result}')
	pdb.close()

	return result

# 20231110 s.j.b 원장변경 수정
@router.post("/jubsu", name="원장변경 접수현황 접수", description="", status_code=201)
def create_ledgerdatabase(
	request:CreateRequest,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
	
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")
	#return sawon_cd
	db = DbLink()
	try:
		qry = """
				select 		jubsu_no
						, 	title 
				from 		info_request 
				where 		pk = :pk
				"""
		bind_arr = {"pk":request.info_request_pk}

		db.execute(qry , bind_arr)
		
		fields = db.get_field_names()
		datas = db.get_datas()
		print(datas)
		jubsu_no, title = datas[0]
		print(jubsu_no,title)
		# jubsu_no = ''.join(map(str,datas[0]))
		# title = ''.join(map(str,datas[1]))

	except OracleError as e:
		print("예외발생1",e)
		db.close()
		raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

	pdb = PostgreLink()
	jubsu_chk = 0
	try:
		qry = """
				select 		count(*) cnt 
				from 		ledger.ledger_database 
				where 		use_yb = %s
				and 		info_request_pk = %s
				"""
		pdb.execute_bind(qry , ("1", request.info_request_pk,))
		pdatas = pdb.get_datas()
		jubsu_chk = pdatas[0][0]
		print("jubsu_chk",jubsu_chk)
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	if jubsu_chk > 0:
		pdb.close()
		db.close()
		raise HTTPException(status_code=404, detail="Request number already  entered.")
		
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
		print(request.info_request_pk,sawon_cd)
		pdb.execute_bind(qry , (request.info_request_pk, jubsu_no, title, sawon_cd, sawon_cd,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		db.close()
		raise HTTPException(status_code=500, detail=f"Database error: {e}")
		
	pdb.close()
	db.close()

# 화면에서 저장버튼 클릭
# 20231110 s.j.b 수정
@router.patch("/jubsu/{ld_pk}", name="원장변경 접수현황 업데이트", description="", status_code=200)
def update_ledgerdatabase(
	ld_pk:int,
	requestSql: str = Form(None),
    is_valid: str = Form(...),
	file: UploadFile = File(None),
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")
	
	pdb = PostgreLink()

	ld_chk =0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database
                 where pk=%s
                   and use_yb ='1'
                   and status_cd ='3'
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pdatas = pdb.get_datas()
		ld_chk = pdatas[0][0]
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ld_chk>0:
		raise HTTPException(status_code=422, detail="완료건은 변경 할 수 없습니다.")

	print(f'requestSql:{requestSql}')
	original_filename = ""
	if not requestSql:
		if file:
			print(f'root_dir : {root_dir}')
			base_path = os.path.join(root_dir,'files','requestFiles')
			print(f'base_path : {base_path}')
			original_filename = file.filename
			# 파일 저장 경로
			file_path = os.path.join(base_path, original_filename)
			file_name, file_extension = os.path.splitext(original_filename)
			count = 1
			modified_filename = ""
			while os.path.exists(file_path):
				# Modify the file name by appending a number
				modified_filename = f"{file_name} ({count}){file_extension}"
				file_path = os.path.join(base_path, modified_filename)
				count += 1
			if modified_filename!="":
				original_filename = modified_filename
			# 파일 저장
			with open(file_path, "wb") as f:
				shutil.copyfileobj(file.file, f)

			with open(file_path, "r", encoding='utf-8') as f:
				requestSql = f.read()
		else: # requestSql 도 없고 파일도 없는 경우엔 SQL검증 체크만 저장
			# raise HTTPException(status_code=423, detail="요청쿼리를 입력하세요.")
			try:
				qry ="""
						update 		ledger.ledger_database
						set 		update_date = current_timestamp
								, 	update_by = %s
								, 	is_valid = %s
						where 		pk = %s
					"""
				pdb.execute_bind(qry , (sawon_cd, is_valid, ld_pk,))
				pdb.commit()
			except PsycopgError as e:
				pdb.close()
				raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	print(f'requestSql:{requestSql}')
	if requestSql:
		try:
			qry ="""
					update 		ledger.ledger_database
					set 		request_sql = %s
							,	response_sql = %s
							, 	update_date = current_timestamp
							, 	update_by = %s
							, 	status_cd = %s
							,	is_valid = %s
							,	request_file = %s
							,	create_file = ''
							,	exec_file = ''
					where 		pk = %s
				"""
			pdb.execute_bind(qry , (requestSql, "", sawon_cd, "2", is_valid, original_filename, ld_pk,))
			pdb.commit()
		except PsycopgError as e:
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

		# try:
		# 	qry =f"""
		# 			update 		ledger.ledger_database
		# 			set 		request_file = %s
		# 				,		create_file = ''
		# 				,		exec_file = ''
		# 			where 		pk = %s
		# 		"""
		# 	pdb.execute_bind(qry , (original_filename, ld_pk,))
		# 	pdb.commit()
		# except PsycopgError as e:
		# 	pdb.close()
		# 	raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	#변경되었기 때문에 생성 목록쿼리도 초기화 
	ldes_chk =0
	try:
		qry ="""
				select count(*) cnt
					from ledger.ledger_database_exec_sql
					where ld_pk=%s
					and use_yb ='1'
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pdatas = pdb.get_datas()
		ldes_chk = pdatas[0][0]
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ldes_chk>0:
		try:
			qry ="""
					update 	ledger.ledger_database_exec_sql
						set 	use_yb ='2'
						where 	ld_pk = %s
				"""
			pdb.execute_bind(qry , (ld_pk,))
			pdb.commit()
		except PsycopgError as e:
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")			
	pdb.close()


# 원장변경화면에서 직접적인 삭제는 없음. 요청게시판에서 상태가 반려처리되면 해당 페이지 call
# 20231110 s.j.b 수정
@router.delete("/jubsu/{ld_pk}", name="원장변경 접수현황 삭제", description="", status_code=204)
def delete_ledgerdatabase(
	ld_pk: int,
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
				update 		ledger.ledger_database
   				set 		use_yb = %s
						, 	update_date = current_timestamp
						, 	update_by = %s
				where 		pk= %s
			"""
		pdb.execute_bind(qry , ("2", sawon_cd, ld_pk,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	pdb.close()

# SQL생성버튼(타입별로 다르게 처리하는 방법, 여러줄에 대한 대응 방법)
# 20231110 s.j.b 수정
@router.post("/jubsu/{ld_pk}/createsql", name="원장변경 접수현황 쿼리 생성", description="", status_code=201)
def create_forecastsql(
	ld_pk: int,
	access_token:str = Depends(sc.get_access_token),
	user_service:UserService = Depends(UserService),
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")
	
	db = DbLink()
	pdb = PostgreLink()
	pdatas=[]

	ld_chk =0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database
                 where pk=%s
                   and use_yb ='1'
                   and status_cd ='3'
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pdatas = pdb.get_datas()
		ld_chk = pdatas[0][0]
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ld_chk>0:
		raise HTTPException(status_code=422, detail="완료건은 변경 할 수 없습니다.")
		
	list_field =[]
	key_list = []

	try:
		qry = """
				select 		request_sql
                        ,   response_sql
						,	is_valid
						,   request_file
						,   create_file
						,   exec_file
				from 		ledger.ledger_database
				where 		pk = %s
			"""
		pdb.execute_bind(qry , (ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
		request_sql, response_sql_chk, is_valid, request_file, create_file, exec_file = pdatas[0]
		print(request_sql)
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	
	if not request_sql:
		raise HTTPException(status_code=422, detail="요청쿼리가 없습니다.")
	
	#초기화 작업
	if response_sql_chk:
		try:
			qry ="""
					update  ledger.ledger_database
					set     response_sql = ''
							, create_file = ''
							, exec_file = ''
					where   pk = %s
				"""
			pdb.execute_bind(qry , (ld_pk,))
			pdb.commit()
		except PsycopgError as e:
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	ldes_chk =0
	try:
		qry ="""
				select count(*) cnt
					from ledger.ledger_database_exec_sql
					where ld_pk=%s
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pdatas = pdb.get_datas()
		ldes_chk = pdatas[0][0]
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ldes_chk>0:
		try:
			qry ="""
					update 	ledger.ledger_database_exec_sql
						set 	use_yb ='2'
						where 	ld_pk = %s
				"""
			pdb.execute_bind(qry , (ld_pk,))
			pdb.commit()
		except PsycopgError as e:
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")	

	request_sql = request_sql.replace('newincar.','').replace('NEWINCAR.','')
	sql_items = request_sql.split(";")

	if len(sql_items)>10001:
		len_sql_items= len(sql_items)
		raise HTTPException(status_code=422, detail=f"10000건 까지만 처리 가능합니다. 관리자에게 문의하세요.")

	# print(f"sql_items:{sql_items}")
	for j, sql_item in enumerate(sql_items, start=1):
		if sql_item:
			print(f"sql_item:{j}{sql_item}")
			# print(f"is_valid:{is_valid}")
			parts = sql_item.split() # 공백 기준으로 나눔
			print(f"parts:{parts}")
			if parts and len(parts) > 0:
				dmlLower = str(parts[0]).lower()
			else:
				continue
			partsListLower = [part.lower() for part in parts] # parts 를 소문자로 변환해서 새로운 list 생성
			if dmlLower=="update" or dmlLower=="delete" or dmlLower=="insert":
				return_list = []
				if dmlLower=="update" and is_valid=="1":
					table_name = str(parts[1]).lower()
					if "where" in partsListLower:
						#set_clause = "".join(parts[3:partsListLower.index("where")]) # 3부터 where 전까지 set 절
						#set_clause = sql_item.split("set")[1].split("where")[0].strip()
						start_index = sql_item.lower().find("set") + len("set")
						end_index = sql_item.lower().find("where")
						set_clause = sql_item[start_index:end_index].strip()
					else:
						raise HTTPException(status_code=422, detail="WHERE 절에 오류가 있습니다.")
					print(f'set_clause : {set_clause}')
					columns = set_clause.split("set_clause") # date타입인 경우에 , 가 있어서 ,로 구분하면 오류발생 columns = set_clause.split(",")
					first_quote_index = set_clause.find("'")
					if first_quote_index == -1: # 변경되는 값이 다른 컬럼인 경우
						raise HTTPException(status_code=422, detail="위 구문은 SQL검증이 불가합니다. SQL검증 체크를 해지하고 저장 하세요.")
					secund_quote_index = set_clause.find("'",set_clause.find("'")+1)
					print(f'secund_quote_index : {secund_quote_index}')
					if ',' in set_clause[secund_quote_index:]:
						print('set_clause : ',set_clause[secund_quote_index:])
						raise HTTPException(status_code=422, detail="SET 절은 하나만 입력 가능합니다.")
					# columns 의 길이가 1보다 크면 오류 처리
					# if len(columns) > 1:
					# 	print(f"columns:{columns}")
					# 	raise HTTPException(status_code=422, detail="SET 절은 하나만 입력 가능합니다.")
					column_names = ""
					set_column =[] #변경 컬럼명 list
					set_value =[] #변경후 값 list
					set_sql_data =[]
					for column in columns:
						print(f"column: {column}")
						enc_index = str(column).lower().find("xx1.enc_varchar2_ins(")
						if enc_index != -1:
							raise HTTPException(status_code=422, detail="위 구문은 SQL검증이 불가합니다. SQL검증 체크를 해지하고 저장 하세요.")
						dec_index = str(column).lower().find("xx1.dec_varchar2_sel(")
						if dec_index != -1:
							raise HTTPException(status_code=422, detail="위 구문은 SQL검증이 불가합니다. SQL검증 체크를 해지하고 저장 하세요.")
						values = column.split("=",1) 
						print(f"values{values}")
						values0 = values[0].strip()
						values1 = values[1].strip()

						to_date_index = str(values1).lower().find("to_date(")
						print(f"to_date_index:{to_date_index}")
						if to_date_index != -1:
							remaining_string = values1[to_date_index + len("to_date("):]
							print(f"remaining_string:{remaining_string}")
							date_argument1 = remaining_string.split(",", 1)[0]
							date_value = date_argument1.strip(" '")
							date_argument2 = remaining_string.split(",", 1)[1]
							
							column_name = "to_char("+values0+","+date_argument2+" as "+values0
							set_column.append(str(values0).lower())
							set_value.append(date_value)
							set_sql_data.append(values1)
						else:
							column_name = values0
							set_column.append(str(values0).lower())
							set_value.append(values1)
							set_sql_data.append(values1)
							# to_enc_index = str(values[1]).lower().find("xx1.enc_varchar2_ins(")
							# if to_enc_index != -1:
							# 	remaining_string = values[1][to_enc_index + len("xx1.enc_varchar2_ins("):]
							# 	enc_argument1 = remaining_string.split(",", 1)[0]
							# 	enc_value = enc_argument1.strip(" '")
							# 	enc_argument2 = remaining_string.split(",", 1)[1]
							# 	enc_argument2 = enc_argument2.upper()
							# 	print(f"enc_argument2{enc_argument2}")
							# 	column_name = "xx1.dec_varchar2_sel("+values[0]+","+enc_argument2+" as "+values[0]
							# 	set_column.append(values[0])
							# 	set_value.append(enc_value)
							# 	set_sql_data.append(values[1].replace('incar_a001','INCAR_A001'))
							# else:
							# 	column_name = values[0]
							# 	set_column.append(values[0])
							# 	set_value.append(values[1])
							# 	set_sql_data.append(values[1])

						#set_value.append(values[1])
						if column_names:
							column_names = column_names+","+column_name
						else:
							column_names = column_name
						print("column_names",column_names)
						

					where_clause = "".join(sql_item[str(sql_item).lower().index("where"):]) # 전체 sql에서 where 부터 끝까지 where절


					try:
						# 오라클에서 해당 테이블의 키필드를 확보한다.
						qry = """
								select 		b.column_name
								from 		all_constraints  a
									, 		all_cons_columns b
								where 		a.table_name      = upper(:table_name)
								and 		a.constraint_type = :constraint_type
								and 		a.owner           = b.owner
								and 		a.constraint_name = b.constraint_name
								order by 	b.position
							"""
						bind_arr = {"constraint_type":"P", "table_name":table_name}

						db.execute(qry , bind_arr)
					
						fields = db.get_field_names()
						datas = db.get_datas()
						print(f"datas:{datas}")
						if len(datas)==0:
							db.close()
							pdb.close()
							raise HTTPException(status_code=422, detail=f"테이블명({table_name})의 primary_key 가 없습니다.")	

						key_list = [row[0].lower() for row in datas]
						
						# 변환된 SELECT 문 생성
						#key_list = ['company_cd','sawon_cd']
						column_names_list = [col.strip() for col in column_names.split(',')] # , 로 나누고 앞뒤공백 제거해서 새로운 list 생성
						for key in key_list:
							if key not in column_names_list: # 변경되는 컬럼에 key 없으면 포함
								column_names += f", {key}"
					except OracleError as e:
						db.close()
						pdb.close()
						print(f"Oracle Database error: {e}")
						raise HTTPException(status_code=500, detail=f"Oracle Database error1: {e}")

					#response_sql = f"select {column_names.lower()} from {table_name} {where_clause}"	
					response_sql = f"select {column_names} from {table_name} {where_clause}"		
					response_sql = response_sql.strip()			
					print(f"response_sql:{response_sql}")
					#print(columns)
					#print(set_column)
					#print(set_value)
					# response_sql 실행
					try:
						bind_arr={}
						# re_response_sql = response_sql.replace(';','')
						# print(f"re_response_sql:{re_response_sql}")
						db.execute(response_sql,{})
						pfields = db.get_field_names()
						pdatas = db.get_datas()
						#print(pdatas)
					except OracleError as e:
						db.close()
						pdb.close()
						print(f"Oracle Database error: {e}")
						# raise HTTPException(status_code=500, detail=f"Oracle Database error2: {e}")
					print(f"pdatas:{pdatas}")
					#if len(pdatas)==0:
						
					try:
						print(f"response_sql:{response_sql}")
						response_sql= response_sql+";"
						if j>1:
							sql = f"update ledger.ledger_database set response_sql=response_sql||'\n'||%s where pk=%s"
						else:
							sql = f"update ledger.ledger_database set response_sql=response_sql||%s where pk=%s"
						pdb.execute_bind(sql,(response_sql,ld_pk,))
						#print(sql)
						#print(response_sql, ld_pk)
					except PsycopgError as e:
						db.close()
						pdb.close()
						print(f"PostgreSQL Database error: {e}")
						raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
					# 생성쿼리를 실행했을때 데이타가 없는 경우
					if len(pdatas)==0:
						new_item = {
								'id': '',
								'column_value': '',
								'before_value': '',
								'after_value': '',
								'status_cd': '3',
								'status_nm': '오류',
								'result_cd': '',
								'result_nm': '',
								'forecast_sql': response_sql
							}
							
						return_list.append(new_item)
					for i, data in enumerate(pdatas, start=1):
						zipped_data = zip(pfields, data)
						forecast_sql=""
						forecast_sql_where=""
						forecast_list=[]
						forecast_list2=[]
						print(">", key_list)
						for field, value in zipped_data:
							print(">>", field, value)
							lower_field = str(field).lower()
							print("set_column",set_column,"lower_field",lower_field)
							if lower_field in set_column:
								print(">>>> set column", lower_field)
								index = set_column.index(lower_field)
								after_value = set_value[index]
								after_sql_data = set_sql_data[index]
								list_json = {"column_value":lower_field,"before_value":value,"after_value":after_value,"after_sql_data":after_sql_data}
								forecast_list.append(list_json)
								print(f'forecast_list : {forecast_list}')
								# update_sql = f"update {table_name} set {field}={after_value} "
								# print(update_sql)
							if lower_field in key_list:
								print(">>>> key column", lower_field)
								try:
									qry = """
											select 	data_type
											from 	all_tab_columns
											where 	table_name = :table_name
											and 	column_name =:column_name
										"""
									bind_arr = {"table_name":table_name.upper(), "column_name":str(field).upper()}
									db.execute(qry , bind_arr)
									column_types = db.get_datas()
									column_type = ''.join(map(str,column_types[0]))

									print(">>>>>>", column_type)
									## 컬럼 타입 까지는 뽑았는데 그 다음에는 뭘하지?
								except OracleError as e:
									db.close()
									db.close()
									raise HTTPException(status_code=500, detail=f"Oracle Database error3: {e}")
								#print(bind_arr)
								#print(field,column_type)
								#column_type=""
								#result2 = {"field":field,"value":value}
								#result_list2.append(result2)
								#print(result2)
								if forecast_sql_where=="":
									if 'char' in column_type.lower():
										forecast_sql_where += f" where {field}='{value}'"
									else:
										forecast_sql_where += f" where {field}={value}"
								else:
									if 'char' in column_type.lower():
										forecast_sql_where += f" and {field}='{value}'"
									else:
										forecast_sql_where += f" and {field}={value}"
								# if key not in key_list:
								# 	updatecolumn_names += f", {key}"
						#update 문 검증
						status_nm=""
						try:
							test_qry = f"select count(*) cnt from {table_name} {forecast_sql_where}"
							print('test_qry',test_qry)
							db.execute(test_qry,{})
							fields = db.get_field_names()
							datas = db.get_datas()
							total_cnt = int(''.join(map(str,datas[0])))
							#print('test_qry',test_qry)
							#print("total_cnt",total_cnt)
							if total_cnt ==1:
								status_cd = "1"
								status_nm = "성공"
							else:
								status_cd="2"
								status_nm = "실패"
						except Exception as e:
							print("oracle 예외발생1",e,test_qry)
							status_cd="3"
							status_nm = "오류"
						print('forecast_sql_where',forecast_sql_where,status_cd,status_nm)
						forecast_list2 = {
								'where':forecast_sql_where, 
								'status_cd':status_cd, 
								'status_nm':status_nm, 
								'result_cd':'1', 
								'result_nm':'실행전',
							}
						print('forecast_list2',forecast_list2)
						forecast_result = [dict(item, **forecast_list2) for item in forecast_list]
						print('forecast_result',forecast_result)
						#print(forecast_result)
						# input_list의 각 딕셔너리에 대해 원하는 형식으로 변환하여 output_list에 추가합니다.
						for idx, item in enumerate(forecast_result, start=1):
							# 새로운 딕셔너리를 생성하고 필드를 추가합니다.
							new_item = {
								'id': '',
								'column_value': item['column_value'],
								'before_value': item['before_value'],
								'after_value': item['after_value'],
								'status_cd': item['status_cd'],
								'status_nm': item['status_nm'],
								'result_cd': item['result_cd'],
								'result_nm': item['result_nm'],
								'forecast_sql': f'update {table_name} set {item["column_value"]}={item["after_sql_data"]} {item["where"]}'
							}
							
							# 결과를 output_list에 추가합니다.
							return_list.append(new_item)
					print(f"return_list{return_list}")		
					# try:
					# 	qry ="""
					# 			update 	ledger.ledger_database_exec_sql
					# 			set 	use_yb ='2'
					# 			where 	ld_pk = %s
					# 		"""
					# 	pdb.execute_bind(qry , (ld_pk,))
					# 	pdb.commit()
					# except PsycopgError as e:
					# 	db.close()
					# 	pdb.close()
					# 	raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
					for data in return_list:
						print(f"data : {data}")
						try:
							qry = f"""
									insert into 	ledger.ledger_database_exec_sql
													(
															pk
														, 	ld_pk
														, 	column_value
														, 	before_value
														, 	after_value
														, 	forecast_sql
														,	status_cd
														, 	use_yb
														, 	create_date
														,	create_by
													) 
											values
													(
															nextval('ledger.seq_ledger_database_exec_sql')
														, 	%s
														, 	%s
														, 	%s
														, 	%s
														,	%s
														,	%s
														, 	'1'
														, 	current_timestamp
														, 	%s
													)
								"""
							pdb.execute_bind(qry , (ld_pk, data["column_value"],data["before_value"],data["after_value"],data["forecast_sql"],data["status_cd"],sawon_cd ))
							print(ld_pk, data["column_value"],data["before_value"],data["after_value"],data["forecast_sql"],sawon_cd )
						except PsycopgError as e:
							db.close()
							pdb.close()
							raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
				elif dmlLower=="delete" and is_valid=="1":#delete
					table_name = parts[2] if parts[1]=='from' else parts[1]

					column_names = ""
					where_clause = "".join(sql_item[str(sql_item).lower().index("where"):])

					# 오라클에서 해당 테이블의 키필드를 확보한다.
					qry = """
							select 		b.column_name
							from 		all_constraints  a
								, 		all_cons_columns b
							where 		a.table_name      = upper(:table_name)
							and 		a.constraint_type = :constraint_type
							and 		a.owner           = b.owner
							and 		a.constraint_name = b.constraint_name
							order by 	b.position
						"""
					bind_arr = {"constraint_type":"P", "table_name":table_name}
					db.execute(qry , bind_arr)

					fields = db.get_field_names()
					datas = db.get_datas()
					if len(datas)==0:
						db.close()
						pdb.close()
						raise HTTPException(status_code=422, detail=f"테이블명({table_name})의 primary_key 가 없습니다.")	
					print(f"datas{datas}")
					key_list = [row[0].lower() for row in datas]
					print(f"key_list{key_list}")
					# 변환된 SELECT 문 생성
					#key_list = ['company_cd','sawon_cd']
					for key in key_list:
						if column_names:
							column_names += f", {key}"
						else:
							column_names += f"{key}"

					response_sql = f"select {column_names} from {table_name} {where_clause}"
					print(response_sql)
					# response_sql 실행
					try:
						bind_arr={}
						db.execute(response_sql,bind_arr)
						pfields = db.get_field_names()
						pdatas = db.get_datas()
						#print(pdatas)
					except OracleError as e:
						db.close()
						pdb.close()
						raise HTTPException(status_code=500, detail=f"Oracle Database error4: {e}")
					#print(pdatas)
					#if len(pdatas)==0:
						
					try:
						# sql = f"update ledger.ledger_database set response_sql = %s where pk = %s"
						response_sql= response_sql+";"
						if j>1:
							sql = f"update ledger.ledger_database set response_sql=response_sql||'\n'||%s where pk=%s"
						else:
							sql = f"update ledger.ledger_database set response_sql=response_sql||%s where pk=%s"
						pdb.execute_bind(sql,(response_sql,ld_pk,))
					except PsycopgError as e:
						db.close()
						pdb.close()
						raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

					if len(pdatas)==0:
						new_item = {
								'id': '',
								'column_value': '',
								'before_value': '',
								'after_value': '',
								'status_cd': '3',
								'status_nm': '오류',
								'result_cd': '',
								'result_nm': '',
								'forecast_sql': response_sql
							}
							
						return_list.append(new_item)
					for i, data in enumerate(pdatas, start=1):
						zipped_data = zip(pfields, data)
						forecast_sql=""
						forecast_sql_where=""
						forecast_list=[]
						forecast_list2=[]
						for field, value in zipped_data:
							lower_field = str(field).lower()
							if lower_field in key_list:
								try:
									qry = """
											select 		data_type
											from 		all_tab_columns
											where 		table_name = :table_name
											and 		column_name =:column_name
										"""
									bind_arr = {"table_name":table_name.upper(), "column_name":str(field).upper()}
									db.execute(qry , bind_arr)
									column_types = db.get_datas()
									column_type = ''.join(map(str,column_types[0]))
								except OracleError as e:
									db.close()
									pdb.close()
									raise HTTPException(status_code=500, detail=f"Oracle Database error5: {e}")
								if forecast_sql_where=="":
									if 'char' in column_type:
										forecast_sql_where += f" where {field}='{value}'"
									else:
										forecast_sql_where += f" where {field}={value}"
								else:
									if 'char' in column_type:
										forecast_sql_where += f" and {field}='{value}'"
									else:
										forecast_sql_where += f" and {field}={value}"
								# if key not in key_list:
								# 	updatecolumn_names += f", {key}"
						#delete 문 검증
						try:
							test_qry = f"select count(*) cnt from {table_name} {forecast_sql_where}"
							db.execute(test_qry,{})
							fields = db.get_field_names()
							datas = db.get_datas()
							total_cnt = int(''.join(map(str,datas[0])))
							#print('test_qry',test_qry)
							#print("total_cnt",total_cnt)
							if total_cnt ==1:
								status_cd = "1"
								status_nm = "성공"
							else:
								status_cd="2"
								status_nm = "실패"
						except Exception as e:
							print("oracle 예외발생1",e,test_qry)
							status_cd="2"
							status_nm = "오류"
						print("forecast_sql_where",forecast_sql_where)
						print("status_cd",status_cd)
						# 새로운 딕셔너리를 생성하고 필드를 추가합니다.
						new_item = {
							'id': '',
							'column_value': '',
							'before_value': '',
							'after_value': '',
							'status_cd': status_cd,
							'status_nm': status_nm,
							'result_cd': "1",
							'result_nm' : "실행전",
							'forecast_sql': f'delete {table_name} {forecast_sql_where}'
						}
						
						# 결과를 output_list에 추가합니다.
						return_list.append(new_item)
					print(return_list)		
					# try:
					# 	qry ="""
					# 			update 		ledger.ledger_database_exec_sql
					# 			set 		use_yb ='2'
					# 			where 		ld_pk = %s
					# 		"""
					# 	pdb.execute_bind(qry , (ld_pk,))
					# 	pdb.commit()
					# except PsycopgError as e:
					# 	db.close()
					# 	pdb.close()
					# 	raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
					for data in return_list:
						try:
							qry = f"""
										insert into 	ledger.ledger_database_exec_sql
														(
																pk
															, 	ld_pk
															, 	column_value
															, 	before_value
															, 	after_value
															, 	forecast_sql
															,	status_cd
															, 	use_yb
															, 	create_date
															,	create_by
														) 
												values
														(
																nextval('ledger.seq_ledger_database_exec_sql')
															, 	%s
															, 	''
															, 	''
															, 	''
															, 	%s
															, 	%s
															, 	'1'
															, 	current_timestamp
															, 	%s
														)
								"""
							pdb.execute_bind(qry , (ld_pk,data["forecast_sql"],data["status_cd"],sawon_cd ))
							#print(ld_pk, data["column_value"],data["before_value"],data["after_value"],data["forecast_sql"],sawon_cd )
						except PsycopgError as e:
							db.close()
							pdb.close()
							raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
				elif dmlLower=="insert" and is_valid=="1":#insert
					sql_item = sql_item.replace('\r\n',' ').strip()
					try:
						if j>1:
							sql = f"update ledger.ledger_database set response_sql=response_sql||'\n'||%s where pk=%s"
						else:
							sql = f"update ledger.ledger_database set response_sql=response_sql||%s where pk=%s"
						pdb.execute_bind(sql,(sql_item,ld_pk,))
						#print(sql)
						#print(response_sql, ld_pk)
					except PsycopgError as e:
						db.close()
						pdb.close()
						print(f"PostgreSQL Database error: {e}")
						raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
					status_cd = '1'
					try:
						db.execute(sql_item,{})
					except OracleError as e:
						print(f"wwwwwwwwwwwwwwwwwwwwww{sql_item}")
						db.rollback()
						status_cd = '2'
					db.rollback()
					try:
						qry = f"""
									insert into 	ledger.ledger_database_exec_sql
													(
															pk
														, 	ld_pk
														, 	column_value
														, 	before_value
														, 	after_value
														, 	forecast_sql
														,	status_cd
														, 	use_yb
														, 	create_date
														,	create_by
													) 
											values
													(
															nextval('ledger.seq_ledger_database_exec_sql')
														, 	%s
														, 	''
														, 	''
														, 	''
														, 	%s
														, 	%s
														, 	'1'
														, 	current_timestamp
														, 	%s
													)
							"""
						pdb.execute_bind(qry , (ld_pk,sql_item,status_cd,sawon_cd ))
						#print(ld_pk, data["column_value"],data["before_value"],data["after_value"],data["forecast_sql"],sawon_cd )
					except PsycopgError as e:
						db.close()
						pdb.close()
						raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

				else:
					sql_item = sql_item.replace('\r',' ')#.replace('\n',' ')
					print(f"is_valid2_sql_item:{sql_item}")
					try:
						if j>1:
							sql = f"update ledger.ledger_database set response_sql=response_sql||'\n'||%s where pk=%s"
						else:
							sql = f"update ledger.ledger_database set response_sql=response_sql||%s where pk=%s"
						pdb.execute_bind(sql,(sql_item,ld_pk,))
						#print(sql)
						#print(response_sql, ld_pk)
					except PsycopgError as e:
						db.close()
						pdb.close()
						print(f"PostgreSQL Database error: {e}")
						raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
					status_cd = '1'
					# try:
					# 	db.execute(sql_item,{})
					# except PsycopgError as e:
					# 	status_cd = '2'
					db.rollback()
					try:
						qry = f"""
									insert into 	ledger.ledger_database_exec_sql
													(
															pk
														, 	ld_pk
														, 	column_value
														, 	before_value
														, 	after_value
														, 	forecast_sql
														,	status_cd
														, 	use_yb
														, 	create_date
														,	create_by
													) 
											values
													(
															nextval('ledger.seq_ledger_database_exec_sql')
														, 	%s
														, 	''
														, 	''
														, 	''
														, 	%s
														, 	%s
														, 	'1'
														, 	current_timestamp
														, 	%s
													)
							"""
						pdb.execute_bind(qry , (ld_pk,sql_item,status_cd,sawon_cd ))
						#print(ld_pk, data["column_value"],data["before_value"],data["after_value"],data["forecast_sql"],sawon_cd )
					except PsycopgError as e:
						db.close()
						pdb.close()
						raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")	
				pdb.commit()

			else:
				pdb.close()
				db.close()
				raise HTTPException(status_code=404, detail="request sql error")

	#파일로 처리한 건은 파일 생성
	if request_file!="" :
		try:
			qry = """
					select 		response_sql
					from 		ledger.ledger_database
					where 		pk = %s
				"""
			pdb.execute_bind(qry , (ld_pk,))
			pfields = pdb.get_field_names()
			pdatas = pdb.get_datas()
			response_sql = pdatas[0][0]
			print(request_sql)
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

		current_time = datetime.now()
		formatted_time = current_time.strftime("%Y%m%d%H%M%S")
		file_name = "createFile_"+str(ld_pk)+"_"+formatted_time+".txt"
		base_path = os.path.join(root_dir,'files','createFiles')
		output_file_path = os.path.join(base_path, file_name)
		with open(output_file_path, 'w', encoding='utf-8') as txt_file:
			txt_file.write(response_sql)

		try:
			sql = """
			update  ledger.ledger_database 
			set     create_file=%s
			where   pk = %s
			"""
			pdb.execute_bind(sql,(file_name, ld_pk,))
			pdb.commit()
		except PsycopgError as e:
			db.close()
			pdb.close()
			print(f"PostgreSQL Database error: {e}")
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	create_execfiles(ld_pk)

	db.close()
	pdb.close()

@router.post("/jubsu/{ld_pk}/confirmsql", name="원장변경 접수현황 검토완료", description="", status_code=201)
def confirm_forecastsql(
	ld_pk: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")
	
	db = DbLink()
	pdb = PostgreLink()	
	ld_chk =0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database
                 where pk=%s
                   and use_yb ='1'
                   and status_cd ='3'
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pdatas = pdb.get_datas()
		ld_chk = pdatas[0][0]
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ld_chk>0:
		db.close()
		pdb.close()
		raise HTTPException(status_code=422, detail="완료건은 변경 할 수 없습니다.")

	#실행할 목록중에 생성결과가 정상이 아닌건이 있으면 진행X
	ldes_chk = 0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database_exec_sql
                 where use_yb = '1'
                   and status_cd <> '1'
                   and ld_pk = %s
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
		ldes_chk = pdatas[0][0]
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ldes_chk>0:
		db.close()
		pdb.close()
		raise HTTPException(status_code=422, detail="생성결과에 정상이 아닌건이 있으면 검토완료 불가합니다.")
	
	try:
		# status_cd = '5' 검토완료
		qry = """
					update 		ledger.ledger_database 
					set 		status_cd = %s
					where 		pk = %s
			"""
		pdb.execute_bind(qry,("5", ld_pk,))
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
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

	try:
		qry = """
                select info_request_pk
                  from ledger.ledger_database
                 where pk=%s
                   and use_yb ='1'
		"""
		pdb.execute_bind(qry,(ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	info_request_pk = pdatas[0][0]
	print(f"systemid{systemid}")
	print(f"info_request_pk{info_request_pk}")

	# 실행이 실패했을 경우에는 다시 진행하게 되므로 use_yb 를 2로 바꾸고 새로 insert
	ld_chk =0
	try:
		qry ="""
                select count(*) cnt
                  from info_confirm_list
                 where arc_pk=:arc_pk
                   and use_yb ='1'
                   and status_cd in ('9','13')
		"""
		db.execute(qry,{"arc_pk":info_request_pk})
		fields = db.get_field_names()
		datas = db.get_datas()
		ld_chk = datas[0][0]
	except OracleError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
	if ld_chk>0:
		try:
			qry = """
                update info_confirm_list
                   set use_yb = '2'
                 where arc_pk=:arc_pk
                   and use_yb ='1'
                   and status_cd in ('9','13')
				"""
			db.execute(qry, {"arc_pk":info_request_pk})
		except OracleError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
	
	try:
		qry = """
			update  info_request_check
			set     dev_check_yb = '1'
					, damdang_check_yb ='1'
			where   arc_pk =:arc_pk 
			"""
		db.execute(qry, {"arc_pk":info_request_pk})
	except OracleError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")

	status_list = [9,13]
	for item in status_list:
		try:
			qry = """
                    update info_request
                       set status_cd =:status_cd
                     where pk = :info_request_pk
			"""
			db.execute(qry,{"status_cd":item,"info_request_pk":info_request_pk})
		except OracleError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"oracle Database error: {e}")
		 
		try:
			qry = """
                    insert into info_confirm_list
                    values
                    (
                        seq_info_confirm_list.nextval
                        , :arc_pk
                        , :status_cd
                        , :create_by
                        , sysdate
                        , '1'
                    )
			"""
			db.execute(qry,{"arc_pk":info_request_pk,"status_cd":item,"create_by":systemid})
		except OracleError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"oracle Database error: {e}")

		time.sleep(2)

	content = f"""□  원장변경 요청 검토완료  □\n접수PK : {info_request_pk}\n작성자 : {sawon_cd}"""
	dataInfo = {'webhook_url':'https://teamroom.nate.com/api/webhook/f3af6d62/l4y0v5TG4fSZWdf94A0drnDb','content':content}
	URL = 'http://was-dos.incar.co.kr/api/giteaApi/webhook'
	response = requests.post(URL, json=dataInfo)
	


	# qry = """
    #             select  ip
    #             from    sawon
    #             where   sawon_cd =:sawon_cd
    #         """
	# pw = ""
	# db.execute(qry,{"sawon_cd":systemid})
	# pfields = db.get_field_names()
	# pdatas = db.get_datas()
	# pw = pdatas[0][0]
	# print(f"pw{pw}")
	# dataInfo = {'registCd':systemid,'registPw':pw,'pk':3702,'gubun':'8'}
	# URL = 'http://devair.incar.co.kr/Etc/InfoRequest/SaveConfirm'
	# response = requests.post(URL, data=dataInfo)
	# print(response.text)
	# if response.status_code == 200:  # 정상 응답 확인
	# 	xml_data = response.text
	# 	root = ET.fromstring(xml_data)  # XML 파싱
	# 	print("root : ",root)
	# 	for status in root.findall('status'):
	# 		value = status.find('ercode').text
	# 		print("value",value)
	# 	# 이제 XML 요소에 접근하여 필요한 작업 수행 가능
	# 	# 예를 들어, 특정 요소의 값을 가져오는 방법은 아래와 같습니다:
	# 	#value = root.find('sawon_cd').text
	# 	#print(value)
	# else:
	# 	print("Error:", response.status_code)

	# dataInfo = {'registCd':'1611006','registPw':pw,'pk':info_request_pk,'gubun':'13'}
	# URL = 'http://devair.incar.co.kr/Etc/InfoRequest/SaveConfirm'
	# response = requests.post(URL, data=dataInfo)
	# print(response.text)
	# if response.status_code == 200:  # 정상 응답 확인
	# 	xml_data = response.text
	# 	root = ET.fromstring(xml_data)  # XML 파싱
	# 	print("root : ",root)
	# 	for status in root.findall('status'):
	# 		value = status.find('ercode').text
	# 		print("value",value)
	# 	# 이제 XML 요소에 접근하여 필요한 작업 수행 가능
	# 	# 예를 들어, 특정 요소의 값을 가져오는 방법은 아래와 같습니다:
	# 	#value = root.find('sawon_cd').text
	# 	#print(value)
	# else:
	# 	print("Error:", response.status_code)

	pdb.commit()
	db.commit()
	pdb.close()
	db.close()

# 20231111 s.j.b
@router.post("/jubsu/{ld_pk}/execsql", name="원장변경 접수현황 쿼리 실행", description="", status_code=201)
def exec_forecastsql(
	ld_pk: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")
	
	db = DbLink()
	pdb = PostgreLink()	
	ld_chk =0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database
                 where pk=%s
                   and use_yb ='1'
                   and status_cd ='3'
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pdatas = pdb.get_datas()
		ld_chk = pdatas[0][0]
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ld_chk>0:
		db.close()
		pdb.close()
		raise HTTPException(status_code=422, detail="완료건은 변경 할 수 없습니다.")

	#실행할 목록중에 생성결과가 정상이 아닌건이 있으면 진행X
	ld_chk = 0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database_exec_sql
                 where use_yb = '1'
                   and status_cd <> '1'
                   and ld_pk = %s
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ld_chk>0:
		db.close()
		pdb.close()
		raise HTTPException(status_code=422, detail="생성결과에 정상이 아닌건이 있으면 실행 불가합니다.")
	#실행할 sql목록
	try:
		qry ="""
				select 		a.pk as id
						, 	a.ld_pk
						, 	a.column_value
						, 	a.before_value
						, 	a.after_value
						, 	a.forecast_sql
						,	a.status_cd 
						,	b.code_nm	as status_nm
						,	a.result_cd 
						,	c.code_nm	as result_nm
				from 		ledger.ledger_database_exec_sql a
							left outer join public.commcode b on a.status_cd = b.code_id and b.cl_code = '3'
							left outer join public.commcode c on a.result_cd = c.code_id and c.cl_code = '4'
				where 		a.use_yb = '1'
				and 		a.ld_pk = %s
		"""
		pdb.execute_bind(qry , (ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	#print(pdatas)
	if len(pdatas)==0:
		db.close()
		pdb.close()
		raise HTTPException(status_code=422, detail=f"SQL생성 먼저 진행하세요.")	
	results = []
	err_chk=0
	result_dict = []
	for data in pdatas:
		json_data = {}
		qry = data[5]
		#delete 는 실행전 변경 row data 를 파일로 저장해서 복구시 사용
		parts = str(qry).lower().split()
		if parts[0]=="delete":
			table_name = parts[2] if parts[1]=='from' else parts[1]
			column_names = ""
			where_clause = "".join(qry[str(qry).lower().index("where"):])
			# backupsql = str(qry).replace("delete","select * from ")
			backupsql = "select * from " + table_name + " " + where_clause
			print("backupsql : ",backupsql)
			try:
				db.execute(backupsql,{})
				pfields2 = db.get_field_names()
				pdatas2 = db.get_datas()
				print(">>", pdatas2)
				for i, data2 in enumerate(pdatas2, start=1):
					append_data = {}
					zipped_data = zip(pfields2, data2)
					append_data = {field: value for field, value in zipped_data}
					result_dict.append(append_data)
			except OracleError as e:
				json_data ={
					'id':data[0],
					'result_cd':'3',
					}
				err_chk +=1
				results.append(json_data)
				continue
				# db.close()
				# pdb.close()
				# raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
		#전체 실행
		update_result_cd = ''
		# try:
		# 	db.execute(qry,{})
		# 	json_data ={
		# 		'id':data[0],
		# 		'result_cd':'2',
		# 		}
		# 	update_result_cd = '2'
		# 	#pdb.commit()
		# except Exception as e:
		# 	json_data ={
		# 		'id':data[0],
		# 		'result_cd':'3',
		# 		}
		# 	update_result_cd = '3'
		# 	#print("예외발생",e)
		# 	#db.rollback()
		# 	#pdb.close()
		# 	err_chk +=1
		# results.append(json_data)

		try:
			db.execute(qry,{})
			update_result_cd = '2'
		except Exception as e:
			update_result_cd = '3'
			json_data ={
				'id':data[0],
				'result_cd':'3',
				}
			err_chk +=1
			results.append(json_data)

		# try:
		# 	#print(result['id'],result['status_cd'])
		# 	qry = """
		# 			update 		ledger.ledger_database_exec_sql 
		# 			set 		result_cd = %s 
		# 			where 		pk =%s
		# 		"""
		# 	pdb.execute_bind(qry,(update_result_cd,data[0],))
		# except PsycopgError as e:
		# 	db.close()
		# 	pdb.close()
		# 	raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	#한개라도 실패면 rollback
	# print(">>", results)
	# print(f"err_chk>> {err_chk}")
	# 전체 성공으로 업데이트하고 아래서 실패건만 다시 업데이트
	try:
		#print(result['id'],result['status_cd'])
		qry = """
				update 		ledger.ledger_database_exec_sql 
				set 		result_cd = %s 
				where 		ld_pk =%s
			"""
		pdb.execute_bind(qry,("2",ld_pk,))
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	print(f'err_chk : {err_chk}')
	if err_chk == 0:
		db.commit()
		#pdb.close()
		try:
			# status_cd = '3' 완료
			qry = """
						update 		ledger.ledger_database 
						set 		status_cd = %s
						where 		pk = %s
				"""
			pdb.execute_bind(qry,("3", ld_pk,))
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	else:
		db.rollback()
		#pdb.close()
		try:
			qry = """
						update 		ledger.ledger_database 
						set 		status_cd = %s
						where 		pk = %s
				"""
			pdb.execute_bind(qry,("4", ld_pk,))
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
		try:
			qry = """
					select info_request_pk
					from ledger.ledger_database
					where pk=%s
					and use_yb ='1'
			"""
			pdb.execute_bind(qry,(ld_pk,))
			pfields = pdb.get_field_names()
			pdatas = pdb.get_datas()
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
		info_request_pk = pdatas[0][0]
		print(f"info_request_pk{info_request_pk}")
		ld_chk =0
		try:
			qry ="""
					select count(*) cnt
					from info_confirm_list
					where arc_pk=:arc_pk
					and use_yb ='1'
					and status_cd in ('9','13','6','10')
			"""
			db.execute(qry,{"arc_pk":info_request_pk})
			fields = db.get_field_names()
			datas = db.get_datas()
			ld_chk = datas[0][0]
		except OracleError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
		print(f'ld_chk : {ld_chk}')
		if ld_chk>0:
			try:
				qry = """
					update info_confirm_list
					set use_yb = '2'
					where arc_pk=:arc_pk
					and use_yb ='1'
					and status_cd in ('9','13','6','10')
					"""
				db.execute(qry, {"arc_pk":info_request_pk})
			except OracleError as e:
				db.close()
				pdb.close()
				raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
		try:
			qry = """
                    update info_request
                       set status_cd ='5'
                     where pk = :info_request_pk
			"""
			db.execute(qry,{"info_request_pk":info_request_pk})
		except OracleError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"oracle Database error: {e}")
		db.commit()
	#실행결과 저장
	print(f'results : {results}')
	for result in results:
		try:
			#print(result['id'],result['status_cd'])
			qry = """
					update 		ledger.ledger_database_exec_sql 
					set 		result_cd = %s 
					where 		pk =%s
					and       	use_yb='1'
				"""
			pdb.execute_bind(qry,(result['result_cd'],result['id'],))
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	# print(f"result_dict{result_dict}")
	#db.rollback()
	#pdb.rollback()
	if len(result_dict)>0:
		json_data_file = json.dumps({'list': result_dict}, indent=4, ensure_ascii=False, default=default_serializer)
		#json_data_file = json.dumps({'list': result_dict}, indent=4, ensure_ascii=False)
		current_time = datetime.now()
		formatted_time = current_time.strftime("%Y%m%d%H%M%S")
		file_name = str(ld_pk)+"_"+formatted_time+".json"
		base_path = os.path.join(root_dir,'datas')
		output_file_path = os.path.join(base_path, file_name)
		with open(output_file_path, 'w', encoding='utf-8') as json_file:
			json_file.write(json_data_file)

		try:
			qry = """
						update 		ledger.ledger_database 
						set 		backup_file = %s 
						where 		pk = %s
				"""
			pdb.execute_bind(qry,(file_name, ld_pk,))
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	
	pdb.commit()
	# create_execfiles(ld_pk)

	pdb.close()
	db.close()
	

#복구접수리스트
@router.get("/revive", name="원장변경 복구현황 목록조회", description="", status_code=200)
def getlist(
    gubun: str = Query(...,description="gubun=0은 선택안함, gubun=1은 접수번호, gubun=2는 접수제목", enum=[0,1,2]),# 선택안함: 0, 접수번호: 1, 접수제목: 2
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
				select      a.pk as id
						,   a.info_request_pk
						,   b.jubsu_no
						,   b.title
						,   a.status_cd
						,   c.code_nm   as status_nm
						,   to_char(a.create_date,'yyyy-mm-dd hh24:mi:ss') as create_date
				from        ledger.ledger_database_revive a
							inner join ledger.ledger_database b on a.ld_pk = b.pk
							inner join public.commcode   c      on a.status_cd  = c.code_id and c.cl_code = 5
				where       a.use_yb ='1'
		"""
		if gubun!=0 and search:
			if gubun==1:
				qry += " and a.jubsu_no = %s "
			if gubun==2:
				qry += " and a.title like %s "
				search = "%"+search+"%"
				params.append(search)

		qry += " order by a.pk desc limit %s offset (%s - 1) * %s"
		params.extend([limit, page, limit])
			
		print("qry:",qry)
		pdb.execute_bind(qry , params)
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	results = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
	#list_field.append({"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]})
	#json_result = [float(numeric) for numeric in items]
	#json_result = [[float(item) if isinstance(item, Decimal) else item for item in row] for row in items]
	#json_datas = json.dumps(items)
	pdb.close()

	return results
		
#복구접수상세
@router.get("/revive/{ldr_pk}", name="원장변경 복구현황 상세화면", description="", status_code=200)
def getdetail(
    ldr_pk:int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:dict = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")

	pdb = PostgreLink()
	try:
		qry = """
				select 		a.pk
				        ,   a.ld_pk 
						,	b.jubsu_no
						,	b.title
				from 		ledger.ledger_database_revive 		a
							inner join ledger.ledger_database   b on a.ld_pk = b.pk
				where 		a.pk = %s
			"""
		pdb.execute_bind(qry , (ldr_pk,))
		fields = pdb.get_field_names()
		datas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	ldr_pk = datas[0][0]
	ld_pk = datas[0][1]
	jubsu_no = datas[0][2]
	title = datas[0][3]
	
	pdatas=[]
	try:
		qry ="""
				select 		a.pk as id
						, 	a.ld_pk
						, 	a.column_value
						, 	a.before_value
						, 	a.after_value
						, 	a.forecast_sql
						,	a.status_cd
						, 	b.code_nm as status_nm
						,	a.result_cd
						,	c.code_nm as result_nm
				from 		ledger.ledger_database_exec_sql a
							inner join public.commcode b on b.cl_code = '3' and b.code_id = a.status_cd
							inner join public.commcode c on c.cl_code = '4' and c.code_id = a.result_cd
				where 		a.use_yb = %s
				and 		a.ld_pk = %s
				order by 	a.pk
		"""
		pdb.execute_bind(qry , ('1', ld_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	result1 = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}

	pdatas=[]
	try:
		qry ="""
                select a.pk as id
                     , a.ldr_pk
                     , a.column_value
                     , a.before_value
                     , a.after_value
                     , a.forecast_sql
	                 , b.code_nm  status_nm
	                 , c.code_nm  result_nm
                  from ledger.ledger_database_revive_sql a
                 inner join public.commcode b on b.cl_code ='7' and b.code_id = a.status_cd
                 inner join public.commcode c on c.cl_code ='8' and c.code_id = a.result_cd
                 where a.use_yb = '1'
                   and a.ldr_pk = %s
                 order by a.pk
		"""
		pdb.execute_bind(qry , (ldr_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	result2 = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
	result = {}
	result['pk'] = ldr_pk
	result['jubsu_no'] = jubsu_no
	result['title'] = title
	result['list'] = result1['list']
	result['list2'] = result2['list']
	pdb.close()

	return result

@router.post("/revive", name="원장변경 복구현황 접수", description="", status_code=201)
def create_revive(
	request:CreateReviveRequest,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")		
	
	db = DbLink()
	pdb = PostgreLink()
	ldr_chk =0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database_revive
                 where ld_pk=%s
                   and use_yb ='1'
                   and status_cd ='3'
		"""
		pdb.execute_bind(qry , (request.ld_pk,))
		pdatas = pdb.get_datas()
		ldr_chk = pdatas[0][0]
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ldr_chk>0:
		raise HTTPException(status_code=422, detail="완료건은 접수 할 수 없습니다.")

	try:
		qry = """
                select info_request_pk
                     , backup_file 
					 , request_sql
                  from ledger.ledger_database 
                 where pk=%s
		"""
		pdb.execute_bind(qry , (request.ld_pk,))
		fields = pdb.get_field_names()
		datas = pdb.get_datas()
		print(datas)
		info_request_pk = datas[0][0]
		backup_file = datas[0][1]
		request_sql = datas[0][2]
		req_parts = str(request_sql).split()
		table_gubun = req_parts[0]
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	print(info_request_pk)
	if info_request_pk=='':
		raise HTTPException(status_code=404, detail="LedgerDatabase Not Found")	
	else:
		try:
			qry = "select nextval('ledger.seq_ledger_database_revive') as ld_pk"
			pdb.execute(qry)
			pdatas = pdb.get_datas()
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
		ldr_pk = pdatas[0][0]
		try:
			qry ="""
                    insert into ledger.LEDGER_DATABASE_REVIVE 
                                    (
                                          pk
                                        , info_request_pk
                                        , ld_pk
                                        , STATUS_CD
                                        , USE_YB
                                        , CREATE_DATE
                                        , CREATE_BY
                                        , UPDATE_DATE
                                        , UPDATE_BY
                                    ) 
                    values
                                    (
                                        %s
                                        , %s
                                        , %s
                                        ,'1'
                                        ,'1'
                                        , current_timestamp
                                        , %s
                                        , current_timestamp
                                        , %s
                                    )
			"""
			pdb.execute_bind(qry , (ldr_pk,info_request_pk, request.ld_pk, sawon_cd,sawon_cd,))
			pdb.commit()
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	if table_gubun=='update':
		#ledgerdatabase_exec_sql 에서 변경전 값과 예상sql을 획득
		try:
			qry = """
                    select column_value
                         , before_value
                         , after_value
                         , forecast_sql 
                      from ledger.ledger_database_exec_sql 
                     where ld_pk=%s 
                       and use_yb ='1'      
			"""
			pdb.execute_bind(qry , (request.ld_pk,))
			pdatas = pdb.get_datas()
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
		for i, data in enumerate(pdatas, start=1):
			#예상sql을 set 이전 set절 set이후 로 나눔
			column_value = data[0]
			before_value = data[1]
			after_value = data[2]
			forecast_sql = data[3]
			print(column_value,before_value,after_value,forecast_sql)
			parts = str(forecast_sql).split()
			print(parts[0],parts[1], parts[2], parts[3])
			table_name = parts[1]
			parts2 = str(forecast_sql).split('set')
			table_clause = parts2[0]
			set_clause = "".join(parts[3:parts.index("where")])
			set_parts = set_clause.split('=')
			set_column = set_parts[0]
			parts3 = str(forecast_sql).split('where')
			where_clause = parts3[1]
			print(table_clause,set_clause,where_clause)
			try:
				qry = """
                        select DATA_TYPE
                          from all_tab_columns
                         where table_name = :table_name
                           and column_name =:column_name
				"""
				bind_arr = {"table_name":table_name.upper(), "column_name":str(set_column).upper()}
				db.execute(qry , bind_arr)
				column_types = db.get_datas()
			except OracleError as e:
				db.close()
				pdb.close()
				raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
			column_type = ''.join(map(str,column_types[0]))
			column_type = column_type.lower()
			#set절을 변경전값으로 바꾸고 다시 sql문을 생성
			if 'char' in column_type:
				to_enc_index = set_parts[1].find("xx1.enc_varchar2_ins(")
				if to_enc_index != -1:
					remaining_string = set_parts[1][to_enc_index + len("xx1.enc_varchar2_ins("):]

					enc_argument = remaining_string.split(",", 1)[1]
					new_forecast_sql = table_clause+" set "+set_column+"=xx1.enc_varchar2_ins('"+before_value+"',"+enc_argument+" where "+where_clause
				else:
					new_forecast_sql = table_clause+" set "+set_column+"='"+before_value+"' where "+where_clause

			elif 'date' in column_type:
				to_date_index = set_parts[1].find("to_date(")
				if to_date_index != -1:
					remaining_string = set_parts[1][to_date_index + len("to_date("):]
					date_argument = remaining_string.split(",", 1)[1]
				new_forecast_sql = table_clause+" set "+set_column+"=to_date('"+before_value+"',"+date_argument+" where "+where_clause
			else:
				new_forecast_sql = table_clause+" set "+set_column+"="+before_value+" where "+where_clause
			print(new_forecast_sql)
			#update 문 검증
			status_nm=""
			try:
				test_qry = f"select count(*) cnt from {table_name} where {where_clause}"
				db.execute(test_qry,{})
				fields = db.get_field_names()
				datas = db.get_datas()
				total_cnt = int(''.join(map(str,datas[0])))
				#print('test_qry',test_qry)
				#print("total_cnt",total_cnt)
				if total_cnt ==1:
					status_cd = "1"
					status_nm = "성공"
				else:
					status_cd="2"
					status_nm = "실패"
			except Exception as e:
				print("oracle 예외발생1",e,test_qry)
				status_cd="3"
				status_nm = "오류"
			# 저장
			try:
				qry = f"""
								insert into ledger.ledger_database_revive_sql
												(
													pk
													, LDR_PK
													, COLUMN_VALUE
													, BEFORE_VALUE
													, AFTER_VALUE
													, FORECAST_SQL
													, STATUS_CD
													, USE_YB
													, CREATE_DATE
													, CREATE_BY
													, RESULT_CD
												) 
								values
												(
													nextval('ledger.seq_ledger_DATABASE_REVIVE_SQL')
													, %s
													, %s
													, %s
													, %s
													, %s
													, %s
													, '1'
													, current_timestamp        
													, %s
													, '1'
												)
				"""
				pdb.execute_bind(qry , (ldr_pk, set_column,after_value,before_value,new_forecast_sql,status_cd,sawon_cd ))
				#print(ld_pk, data["column_value"],data["before_value"],data["after_value"],data["forecast_sql"],sawon_cd )
			except PsycopgError as e:
				db.close()
				pdb.close()
				raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	else:
		db2 = DbLink() #delete 복구 검증용

		table_name = req_parts[1]

		with open('./datas/'+str(backup_file), 'r', encoding='utf-8') as json_file:
			data = json.load(json_file)
			data_list = data['list']
		for item in data_list:
			for key, value in item.items():
				try:
					qry = """
                        select DATA_TYPE
                          from all_tab_columns
                         where table_name = :table_name
                           and column_name =:column_name
					"""
					bind_arr = {"table_name":str(table_name).upper(), "column_name":str(key).upper()}
					db.execute(qry , bind_arr)
					column_types = db.get_datas()
				except OracleError as e:
					db.close()
					pdb.close()
					raise HTTPException(status_code=500, detail=f"Oracle Database error: {e}")
				column_type = ''.join(map(str,column_types[0]))
				column_type = column_type.lower()
				if "date" in column_type:
					if value is not None:
						item[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
					else:
						item[key] = ''
				else:
					if value is None:
						item[key] = ''


			columns = ', '.join(item.keys())
			values = ', '.join([f"'{value}'" if not isinstance(value, datetime) else f"TO_DATE('{value.strftime('%Y-%m-%d %H:%M:%S')}', 'YYYY-MM-DD HH24:MI:SS')" for value in item.values()])
			#values = ', '.join(['%s' for _ in item.values()])
			#values = ', '.join([f"'{value}'" for value in item.values()])
			new_forecast_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({values})"
			print(f"new_forecast_sql{new_forecast_sql}")

			try:
				db2.execute(new_forecast_sql,{})
				status_cd = "1"
				status_nm = "성공"
			except Exception as e:
				print("oracle 예외발생1",e,new_forecast_sql)
				status_cd="3"
				status_nm = "오류"
			db2.rollback()
			db2.close()

			try:
				qry = f"""
                                    insert into ledger.ledger_database_revive_sql
                                                    (
                                                        pk
                                                        , LDR_PK
                                                        , COLUMN_VALUE
                                                        , BEFORE_VALUE
                                                        , AFTER_VALUE
                                                        , FORECAST_SQL
                                                        , STATUS_CD
                                                        , USE_YB
                                                        , CREATE_DATE
                                                        , CREATE_BY
                                                        , RESULT_CD
                                                    ) 
                                    values
                                                    (
                                                        nextval('ledger.seq_ledger_DATABASE_REVIVE_SQL')
                                                        , %s
                                                        , ''
                                                        , ''
                                                        , ''
                                                        , %s
                                                        , %s
                                                        , '1'
                                                        , current_timestamp        
                                                        , %s
                                                        , '1'
                                                    )
						"""
				pdb.execute_bind(qry , (ldr_pk, new_forecast_sql, status_cd, sawon_cd ))
				#print(ld_pk, data["column_value"],data["before_value"],data["after_value"],data["forecast_sql"],sawon_cd )
			except PsycopgError as e:
				db.close()
				pdb.close()
				raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	pdb.commit()
	pdb.close()
	db.close()

#복구삭제
@router.delete("/revive/{ldr_pk}", name="원장변경 복구현황 삭제", description="", status_code=204)
def delete_revive(
	ldr_pk: int,
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
                update ledger.ledger_database_revive
                   set use_yb ='2'
                     , update_date = current_timestamp
                     , update_by=%s
                 where pk=%s
		"""
		pdb.execute_bind(qry , (sawon_cd, ldr_pk,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	pdb.close()

#복구실행
@router.post("/revive/{ldr_pk}/execsql", name="원장변경 복구현황 실행", description="", status_code=201)
def exec_revive(
	ldr_pk: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")

	db = DbLink()
	pdb = PostgreLink()	
	ldr_chk =0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database_revive
                 where pk=%s
                   and use_yb ='1'
                   and status_cd ='3'
		"""
		pdb.execute_bind(qry , (ldr_pk,))
		pdatas = pdb.get_datas()
		ldr_chk = pdatas[0][0]
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ldr_chk>0:
		db.close()
		pdb.close()
		raise HTTPException(status_code=422, detail="완료건은 변경 할 수 없습니다.")

	#실행할 목록중에 생성결과가 성공이 아닌건이 있으면 진행X
	ldr_chk = 0
	try:
		qry ="""
                select count(*) cnt
                  from ledger.ledger_database_revive_sql
                 where use_yb = '1'
                   and status_cd <> '1'
                   and ldr_pk = %s
		"""
		pdb.execute_bind(qry , (ldr_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	if ldr_chk>0:
		db.close()
		pdb.close()
		raise HTTPException(status_code=422, detail="생성결과에 정상이 아닌건이 있으면 진행 불가합니다.")
	try:
		#실행할 sql목록
		qry ="""
                select a.pk as id
                     , a.ldr_pk
                     , a.column_value
                     , a.before_value
                     , a.after_value
                     , a.forecast_sql
                     , a.status_cd  
	                 , b.code_nm as status_nm
	                 , a.result_cd 
	                 , c.code_nm  as result_nm
                  from ledger.ledger_database_revive_sql a
                       inner join public.commcode b on a.status_cd = b.code_id and b.cl_code='7'
                       inner join public.commcode c on a.result_cd = c.code_id and c.cl_code='8'
                 where a.use_yb = '1'
                   and ldr_pk = %s
                 order by a.pk
		"""
		pdb.execute_bind(qry , (ldr_pk,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		db.close()
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	#print(pdatas)
	results = []
	err_chk=0
	for data in pdatas:
		json_data = {}
		qry = data[5]
		print(f"qry{qry}")
		#전체 실행
		try:
			db.execute(qry,{})
			json_data ={
						'id':data[0],
						'ldr_pk':data[1], 
						'column_value':data[2], 
						'before_value':data[3], 
						'after_value':data[4], 
						'forecast_sql':qry, 
						'status_cd':data[6],
						'status_nm':data[7],
						'result_cd':'2',
						'result_nm':'성공',
						}
			#pdb.commit()
		except Exception as e:
			json_data ={
						'id':data[0],
						'ldr_pk':data[1], 
						'column_value':data[2], 
						'before_value':data[3], 
						'after_value':data[4], 
						'forecast_sql':qry, 
						'status_cd':data[6],
						'status_nm':data[7],
						'result_cd':'3',
						'result_nm':'실패',
						}
			print("예외발생",e)
			#db.rollback()
			#pdb.close()
			err_chk +=1
		results.append(json_data)
	print(f"err_chk{err_chk}")
	#한개라도 실패면 rollback
	if err_chk==0:
		db.commit()
		try:
			qry = """
                    update ledger.ledger_database_revive
                       set status_cd = '2' 
                     where pk =%s
				"""
			pdb.execute_bind(qry,(ldr_pk,))
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	else:
		db.rollback()
		try:
			qry = """
                    update ledger.ledger_database_revive
                       set status_cd = '3' 
                     where pk =%s
				"""
			pdb.execute_bind(qry,(ldr_pk,))
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	#실행결과 저장
	print(f"results{results}")
	for result in results:
		try:
			qry = """
                    update ledger.ledger_database_revive_sql 
                       set result_cd = %s 
                     where pk =%s
 				"""
			pdb.execute_bind(qry,(result['result_cd'],result['id'],))
		except PsycopgError as e:
			db.close()
			pdb.close()
			raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	
	pdb.commit()
	pdb.close()
	db.close()

@router.get("/download/{path_gubun}/{file_name}", name="파일 다운로드", description="", status_code=200)
def download_file(
	path_gubun:str,
    file_name:str,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:dict = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")

	# return file_name
	file_path = os.path.join(f"./files/{path_gubun}", file_name)
	print(file_path)
	if os.path.exists(file_path):
		print("success")
		content_disposition = f'attachment; filename="{file_name}"'
		headers = {'Content-Disposition': content_disposition}
		return FileResponse(path=file_path, filename=file_name, media_type="application/octet-stream", headers=headers)
	else:
		print("error")
		raise HTTPException(status_code=404, detail="File not found")	


@router.post("/test", name="원장변경 접수현황 검토완료", description="", status_code=201)
def confirm_forecastsql(
	ld_pk: int,
	# access_token:str=Depends(sc.get_access_token),
	# user_service:UserService=Depends(UserService),
):
	# code:str = user_service.decode_jwt(access_token=access_token)
	# sawon_cd:str|None = user_service.get_regist_info(code=code)
	# if not sawon_cd:
	# 	raise HTTPException(status_code=404, detail="User Not Found")
	#
# 	db = DbLink()
# 	try:
# 		qry = """
# update    info_request
# set     status_cd = '7'
# where   pk =4832
# 		"""
# 		db.execute(qry,{})
# 	except OracleError as e:
# 		db.close()
# 		raise HTTPException(status_code=500, detail=f"oracle Database error: {e}")
	
# 	try:
# 		qry = """
# update    info_confirm_list
# set     create_date = to_date('20240403112015','yyyymmddhh24miss')
# where   arc_pk = 5084
# and     status_cd ='9'
# 		"""
# 		db.execute(qry,{})
# 	except OracleError as e:
# 		db.close()
# 		raise HTTPException(status_code=500, detail=f"oracle Database error: {e}")
	
# 	try:
# 		qry = """
# update    info_confirm_list
# set     create_date = to_date('20240403112017','yyyymmddhh24miss')
# where   arc_pk = 5084
# and     status_cd ='13'
# 		"""
# 		db.execute(qry,{})
# 	except OracleError as e:
# 		db.close()
# 		raise HTTPException(status_code=500, detail=f"oracle Database error: {e}")
	
	# db.commit()
	# db.close()

	pdb = PostgreLink()	

	try:
		qry = """
update 	job.job_templates
set 	execution_script = 'logFile="/home/batch/calc_susuryo/log/fee200_"$(date "+%Y%m%d%H%M")".log"
nohup /bin/bash /home/batch/calc_susuryo/fee200.sh > ${logFile}'
where 	pk = 97
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()
	try:
		qry = """
update 	job.job_templates
set 	execution_script = 'logFile="/home/batch/calc_susuryo/log/fee400_"$(date "+%Y%m%d%H%M")".log"
nohup /bin/bash /home/batch/calc_susuryo/fee400.sh > ${logFile}'
where 	pk = 98
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()
	try:
		qry = """
update 	job.job_templates
set 	execution_script = 'logFile="/home/batch/calc_susuryo/log/fee180_"$(date "+%Y%m%d%H%M")".log"
nohup /bin/bash /home/batch/calc_susuryo/fee180.sh > ${logFile}'
where 	pk = 92
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()		
	try:
		qry = """
update 	job.job_templates
set 	execution_script = 'logFile="/home/batch/calc_susuryo/log/fee160_"$(date "+%Y%m%d%H%M")".log"
nohup /bin/bash /home/batch/calc_susuryo/fee160.sh > ${logFile}'
where 	pk = 93
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()	
	try:
		qry = """
update 	job.job_templates
set 	execution_script = 'logFile="/home/batch/calc_susuryo/log/fee300_"$(date "+%Y%m%d%H%M")".log"
nohup /bin/bash /home/batch/calc_susuryo/fee300.sh > ${logFile}'
where 	pk = 96
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()	
	try:
		qry = """
update 	job.job_templates
set 	execution_script = 'logFile="/home/batch/calc_susuryo/log/fee550_"$(date "+%Y%m%d%H%M")".log"
nohup /bin/bash /home/batch/calc_susuryo/fee550.sh > ${logFile}'
where 	pk = 99
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()	
	try:
		qry = """
update 	job.job_templates
set 	execution_script = 'logFile="/home/batch/calc_susuryo/log/fee450_"$(date "+%Y%m%d%H%M")".log"
nohup /bin/bash /home/batch/calc_susuryo/fee450.sh > ${logFile}'
where 	pk = 100
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()	
	try:
		qry = """
update job.job_templates
set 	name = '상품비교설명서 데이터 추출-영업부문총괄(매주 수요일)'
where pk =63
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()
	try:
		qry = """
insert into job.job_templates
(pk, name, gubun, status, description, execution_script, build_schedule, use_yb, create_date, create_by, create_name, update_date, update_by, update_name)
values
(nextval('job.seq_job_templates')
, '12차월-관리자'
, '3'
, '1'
, ''
, 'sh /home/project/batchFile/script/dataPrc045.sh'
, '00 09 1 * *'
, '1'
, current_timestamp
, '1611006'
, '오승환'
, current_timestamp
, '1611006'
, '오승환')
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()
	try:
		qry = """
insert into job.job_templates
(pk, name, gubun, status, description, execution_script, build_schedule, use_yb, create_date, create_by, create_name, update_date, update_by, update_name)
values
(nextval('job.seq_job_templates')
, 'FA고지의무 데이터 추출-PA부문총괄(매주 금요일)'
, '3'
, '1'
, ''
, 'sh /home/project/batchFile/script/dataExt010.sh 001046'
, '30 08 * * 5'
, '1'
, current_timestamp
, '1611006'
, '오승환'
, current_timestamp
, '1611006'
, '오승환')
		"""
		pdb.execute(qry)
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")		
	pdb.commit()									
																											 
	pdb.close()

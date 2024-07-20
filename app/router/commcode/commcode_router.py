# -*- coding: utf-8 -*-
from fastapi import APIRouter, Query, Depends, HTTPException, Form
from app.database.postgre import PostgreLink
from pydantic import BaseModel
from app.service.user import UserService
from app.routers.userInfo import security as sc
from psycopg2 import Error as PsycopgError
from app.models.commCodeModels import CreateClcode, UpdateClcode, CreateCode, UpdateCode
router = APIRouter(
    prefix="/api/commcode",
)

@router.get("/codeclass", name="코드클래스 조회", description="", status_code=200)
def getlist_codeclass(
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:dict = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=403, detail="User Not Found")
	if not code:
		raise HTTPException(status_code=404, detail="Access_token Not Found")
		
	pdb = PostgreLink()
	pdatas=[]
	try:
		qry = """
            select  cl_code
                    , cl_name
                    , cl_description
            from 	public.commclcode
            where 	use_yb ='1'
            order by cl_code desc
				"""
		pdb.execute(qry)
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	results = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
	pdb.close()

	return results

@router.get("/codeclass/{cl_code}", name="코드클래스 상세", description="", status_code=200)
def get_codeclass(
    cl_code: int,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:dict = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=403, detail="User Not Found")
	if not code:
		raise HTTPException(status_code=404, detail="Access_token Not Found")
		
	pdb = PostgreLink()
	list_field =[]
	pdatas=[]
	params=[]
	try:
		qry = """
            select  cl_code
                    , cl_name
                    , cl_description
            from 	public.commclcode
            where 	cl_code = %s
			"""
		pdb.execute_bind(qry , ( cl_code,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	result = {}
	for i, data in enumerate(pdatas, start=1):
		result = {field:value for field, value in zip(pfields, data)}

	try:
		qry = """
            select 	cl_code
					, code_id 
                    , code_nm 
                    , code_description 
                    , order_no
            from 	public.commcode
            where 	cl_code = %s
            and 	use_yb ='1'
            order by code_id desc
				"""
		pdb.execute_bind(qry, (cl_code,))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	#results = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
	result['list'] = [{field:value for field, value in zip(pfields, data)} for data in pdatas]
	pdb.close()

	return result
    
@router.post("/codeclass", name="코드 클래스 저장", description="", status_code=201)
def create_codeclass(
	request:CreateClcode,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
	
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")
	#return sawon_cd

	pdb = PostgreLink()
	chk = 0
	try:
		qry = """
				select 		count(*) cnt 
				from 		public.commclcode 
				where 		use_yb = %s
				and 		cl_code = %s
				"""
		pdb.execute_bind(qry , ("1", request.cl_code,))
		pdatas = pdb.get_datas()
		chk = pdatas[0][0]
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	if chk > 0:
		pdb.close()
		raise HTTPException(status_code=404, detail="Request number already  entered.")
		
	try:
		qry ="""
				insert into 	public.commclcode 
								(
										cl_code
									, 	cl_name
									, 	cl_description
									, 	use_yb
									, 	create_date
									, 	create_by
									, 	update_date
									,	update_by
								) 
				values
								(
										%s
									, 	%s
									, 	%s
									, 	'1'
									, 	current_timestamp
									, 	%s
									, 	current_timestamp
									, 	%s
								)
			"""

		pdb.execute_bind(qry , (request.cl_code, request.cl_name, request.cl_description, sawon_cd, sawon_cd,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"Database error: {e}")
		
	pdb.close()

@router.patch("/codeclass/{cl_code}", name="코드 클래스 수정", description="", status_code=200)
def update_codeclass(
	cl_code:int,
    request : UpdateClcode,
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
                update 		public.commclcode
                set 		cl_name = %s
                        ,	cl_description = %s
                        , 	update_date = current_timestamp
                        , 	update_by = %s
                where 		cl_code = %s
            """
		pdb.execute_bind(qry , (request.cl_name, request.cl_description, sawon_cd, cl_code,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	pdb.close()

@router.delete("/codeclass/{cl_code}", name="코드 클래스 삭제", description="", status_code=204)
def delete_codeclass(
	cl_code:int,
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
                update 		public.commclcode
                set 		use_yb ='2'
                        , 	update_date = current_timestamp
                        , 	update_by = %s
                where 		cl_code = %s
            """
		pdb.execute_bind(qry , (sawon_cd, cl_code,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	pdb.close()


@router.get("/code/{cl_code}/{code_id}", name="코드 상세", description="", status_code=200)
def get_code(
    cl_code: int,
	code_id: str,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:dict = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=403, detail="User Not Found")
	if not code:
		raise HTTPException(status_code=404, detail="Access_token Not Found")
		
	pdb = PostgreLink()
	list_field =[]
	pdatas=[]
	params=[]
	try:
		qry = """
			select  cl_code
					, code_id
					, code_nm
					, code_description
			from 	public.commcode
			where 	cl_code = %s
			and 	code_id = %s
			"""
		pdb.execute_bind(qry , ( cl_code, code_id, ))
		pfields = pdb.get_field_names()
		pdatas = pdb.get_datas()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")
	result = {}
	for i, data in enumerate(pdatas, start=1):
		result = {field:value for field, value in zip(pfields, data)}

	pdb.close()

	return result
    
@router.post("/code", name="코드 저장", description="", status_code=201)
def create_code(
	request:CreateCode,
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
	
):
	code:str = user_service.decode_jwt(access_token=access_token)
	sawon_cd:str|None = user_service.get_regist_info(code=code)
	if not sawon_cd:
		raise HTTPException(status_code=404, detail="User Not Found")
	#return sawon_cd

	pdb = PostgreLink()
	chk = 0
	try:
		qry = """
			select 		count(*) cnt 
			from 		public.commcode 
			where 		use_yb = %s
			and 		cl_code = %s
			and 		code_id = %s
			"""
		pdb.execute_bind(qry , ("1", request.cl_code, request.code_id,))
		pdatas = pdb.get_datas()
		chk = pdatas[0][0]
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	if chk > 0:
		pdb.close()
		raise HTTPException(status_code=404, detail="Request number already  entered.")
		
	try:
		qry ="""
				insert into 	public.commcode 
								(
										cl_code
									,	code_id
									, 	code_nm
									, 	code_description
									, 	use_yb
									, 	order_no
									, 	create_date
									, 	create_by
									, 	update_date
									,	update_by
								) 
				values
								(
										%s
									, 	%s
									, 	%s
									, 	%s
									, 	'1'
									,	1
									, 	current_timestamp
									, 	%s
									, 	current_timestamp
									, 	%s
								)
			"""

		pdb.execute_bind(qry , (request.cl_code, request.code_id, request.code_nm, request.cl_description, sawon_cd, sawon_cd,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"Database error: {e}")
		
	pdb.close()

@router.patch("/code/{cl_code}/{code_id}", name="코드 수정", description="", status_code=200)
def update_code(
	cl_code:int,
	code_id:str,
    request : UpdateCode,
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
			update 		public.commcode
			set 		code_nm = %s
					,	code_description = %s
					, 	update_date = current_timestamp
					, 	update_by = %s
			where 		cl_code = %s
			and 		code_id = %s
            """
		pdb.execute_bind(qry , (request.code_nm, request.code_description, sawon_cd, cl_code, code_id,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	pdb.close()

@router.delete("/code/{cl_code}/{code_id}", name="코드 삭제", description="", status_code=204)
def delete_code(
	cl_code:int,
	code_id:str,
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
			update 		public.commcode
			set 		use_yb ='2'
					, 	update_date = current_timestamp
					, 	update_by = %s
			where 		cl_code = %s
			and 		code_id = %s
            """
		pdb.execute_bind(qry , (sawon_cd, cl_code, code_id,))
		pdb.commit()
	except PsycopgError as e:
		pdb.close()
		raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	pdb.close()

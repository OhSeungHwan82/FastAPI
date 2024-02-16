# -*- coding: utf-8 -*-
from fastapi import APIRouter, Query, Depends, HTTPException
from app.database.postgre import PostgreLink
from pydantic import BaseModel
from app.service.user import UserService
from app.routers.userInfo import security as sc
from psycopg2 import Error as PsycopgError

router = APIRouter(
    prefix="/api/public",
)

@router.get("/commcode", name="공통코드 조회", description="", status_code=200)
def getlist(
	cl_code: int = Query(None,description="가져올 공통코드의 CL_CODE리스트, 콤마로 구별한다"),
	use_yb: str = Query(None,description="가져올 공통코드의 CL_CODE리스트의 사용여부"),
	access_token:str=Depends(sc.get_access_token),
	user_service:UserService=Depends(UserService),
):
	code:dict = user_service.decode_jwt(access_token=access_token)
	# sawon_cd:str|None = user_service.get_regist_info(code=code)
	# if not sawon_cd:
	# 	raise HTTPException(status_code=403, detail="User Not Found")
	if not code:
		raise HTTPException(status_code=404, detail="Access_token Not Found")
		
	pdb = PostgreLink()
	list_field =[]
	pdatas=[]
	params=[]
	qry = """
			select 		cl_code
					,	code_id
					,	code_nm
					,	use_yb
			from		public.commcode
			where 		cl_code = %s
			and         use_yb in ('1')
			order by	cl_code, order_no
			"""
	print("qry:",cl_code)
	pdb.execute_bind(qry, (cl_code,))
	pfields = pdb.get_field_names()
	pdatas = pdb.get_datas()
	# except PsycopgError as e:
	# 	pdb.close()
	# 	raise HTTPException(status_code=500, detail=f"PostgreSQL Database error: {e}")

	results = {"list":[{field:value for field, value in zip(pfields, data)} for data in pdatas]}
	pdb.close()

	return results

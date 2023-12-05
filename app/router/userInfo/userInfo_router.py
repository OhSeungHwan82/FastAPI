from fastapi import APIRouter, Depends, HTTPException
from app.database.orcl import DbLink
from pydantic import BaseModel
from jose import jwt
from datetime import date, datetime, timedelta
from . import security as sc
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/userInfo")


class LogIn(BaseModel):
	sawon_cd: str
	password: str

secret_key:str = "601288852c4b2da00b63eab830698195c84c75614b879d348518cc31f588af2a"
jwt_algorithm:str = "HS256"

@router.post("/logIn", description="사용자 로그인 API",
    responses={
        200: {
            "content":{
                "application/json":{
                    "example":{
                        "message":"사용자 로그인에 성공했습니다",
                        "data": {
                            "accessToken":"token",
                            "userInfo":{
                                "sawonCode": "000000",
                                "sawonName": "홍길동"
                            }
                        }
                    }
                }
            }
        }
    }
)
def user_log_in(userInfo:LogIn):
	db = DbLink()

	try:
		qry = """select count(*) cnt from inlinecode where create_by = :sawon_cd and code=:password and expire_date>sysdate
	"""
		bind_arr = {"sawon_cd":userInfo.sawon_cd,"password":userInfo.password}
		db.execute(qry , bind_arr)
		fields = db.get_field_names()
		datas = db.get_datas()
		total_rec = datas[0][0]
		if total_rec == 0:
			#return_msg = "접속정보가 올바르지 않습니다."
			#return return_msg
			raise HTTPException(status_code=404, detail="1111Login Error"+userInfo.sawon_cd+"/"+userInfo.password)
		else:
			access_token = jwt.encode(
            {
                "sub":userInfo.password,
                "exp":datetime.now()+timedelta(hours=4)
            }, 
            secret_key, 
            algorithm=jwt_algorithm
            )
			
			return {
                "message":"사용자 로그인에 성공했습니다",
                "data":{
                    "accessToken": access_token,
                    "userInfo":{
                        "sawon_cd":userInfo.sawon_cd
                    }
                }
            }

	except HTTPException as he:
		print("HTTP에러", he)
		db.close()
		raise HTTPException(status_code=404, detail="222Login Error"+userInfo.sawon_cd+"/"+userInfo.password)
	except Exception as e:
		print("예외발생",e)
		db.close()
		return False

	db.close()

@router.post("/access_token_test")
def access_token_test(access_token:str=Depends(sc.get_access_token)):
	payload:dict = jwt.decode(
		access_token, secret_key, algorithms=[jwt_algorithm]
	)
	sawon_cd =  payload["sub"]
	db = DbLink()

	try:
		qry = """
SELECT code
  FROM inlinecode
 where create_by =:sawon_cd
ORDER BY create_date DESC
FETCH FIRST 1 ROW ONLY
	"""
		bind_arr = {"sawon_cd":sawon_cd}
		db.execute(qry , bind_arr)
		fields = db.get_field_names()
		datas = db.get_datas()
		code_data = ''.join(map(str,datas[0]))
		return code_data

	except Exception as e:
		print("예외발생",e)
		db.close()
		return False
	db.close()

	

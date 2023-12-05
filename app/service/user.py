
from jose import jwt
from app.database.orcl import DbLink
from fastapi import HTTPException
from datetime import date, datetime, timedelta

class UserService:
    encoding:str = "UTF-8"
    secret_key:str = "601288852c4b2da00b63eab830698195c84c75614b879d348518cc31f588af2a"
    jwt_algorithm:str = "HS256"

    def create_jwt(self, code:str)->str:
        return jwt.encode(
            {
                "sub":code,
                "exp":datetime.now()+timedelta(seconds=10)
            }, 
            self.secret_key, 
            algorithm=self.jwt_algorithm
            )

    def decode_jwt(self, access_token:str):
        payload:dict = jwt.decode(
            access_token, self.secret_key, algorithms=[self.jwt_algorithm]
        )
        #exp =  payload["exp"]
        expiration_time = datetime.utcfromtimestamp(payload['exp'])
        current_time = datetime.now()
        if current_time < expiration_time:
            print("토큰이 아직 유효합니다.",expiration_time,current_time)
        else:
            print("토큰이 만료되었습니다")
            raise HTTPException(status_code=404, detail="Token has expired")
        code =  payload["sub"]
        return code

    def get_regist_info(self,code:str):
        db = DbLink()

        try:
            qry = """select create_by as sawon_cd from inlinecode where code=:password
        """
            bind_arr = {"password":code}
            db.execute(qry , bind_arr)
            fields = db.get_field_names()
            datas = db.get_datas()
            sawon_cd = ''.join(map(str,datas[0]))

            if sawon_cd=="":
                return_msg = "접속정보가 올바르지 않습니다."
                return return_msg
            else:
                return sawon_cd

        except Exception as e:
            print("예외발생",e)
            db.close()
            return False
        db.close()


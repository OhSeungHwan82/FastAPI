# -*- coding: utf-8 -*-
from fastapi import APIRouter
from app.database.postgre import PostgreLink
from app.database.orcl import DbLink
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/incarinfo",
)

@router.get("/getIncarInfo")
def getIncarInfo():
	pdb = PostgreLink()
	qry = "select to_char(create_date - interval '5 min', 'yyyy-mm-dd hh24:mi:ss') crt_dtm from incar_info_log"
	pdb.execute(qry)
	
	fields = pdb.get_field_names()

	datas = pdb.get_datas()

	pdb.close()

	if not datas:
		start_time = '1999-01-01 00:00:00'

	start_time = datas[0][0][:20]

	db = DbLink()

	qry = """select      sawon_cd
					,   company_cd
					,   name_kor
			from        sawon
			where       create_date > to_date(:start_time, 'yyyy-mm-dd hh24:mi:ss')
			order by    sawon_cd
	"""
	bind_arr = {"start_time":start_time}

	db.execute(qry , bind_arr)
	
	fields = db.get_field_names()
	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'

	# postgre 재연결
	# pdb = PostgreLink()

	# for data in datas:
	# 	qry = """insert into sawon (sawon_cd, company_cd, name_kor) values (%s, %s, %s)
	# 			on conflict (sawon_cd)
	# 			do update
	# 			set sawon_cd = %s, company_cd = %s, name_kor = %s
	# 	"""
	# 	pdb.execute_bind(qry, data+data)
	# 	pdb.commit()

	# qry = "insert into incar_info_log (table_name, create_date) values ('sawon', now())"
	# pdb.execute(qry)
	# pdb.commit()

	# pdb.close()
	
	return 'OK'

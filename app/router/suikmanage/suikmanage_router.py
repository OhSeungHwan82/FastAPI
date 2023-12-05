# -*- coding: utf-8 -*-
from fastapi import APIRouter
from app.database.orcl import DbLink
from pydantic import BaseModel
import math

router = APIRouter(
    prefix="/api/suikmanage",
)

class SuikListItem(BaseModel):
	stdYear: str
	dept_code1: str = None
	dept_code2: str = None
	dept_code3: str = None
	dept_code4: str = None
	dept_code5: str = None
	fc_code: str = None

@router.post("/list")
def suik_list(item: SuikListItem):
	#db = RDB_client('NEWINCAR','NEWSTART', 'racscan.incar.co.kr', 1521, 'PDB_ONE.INCAR.CO.KR')
	db = DbLink()
	
	# sc
	#sql = f"select * from sawon where sawon_cd = '"+item.sawon_cd+"'"
	#db.execute_sql(sql)
	# bi
	#sql = f"select * from sawon where sawon_cd = :sawon_cd"
	#db.execute(sql , {'sawon_cd' : item.fc_code})

	qry = """select listagg(close_ym, ',') within group (order by close_ym) as close_yms
                  from ( select to_char(add_months(to_date(:start_woldo, 'YYYYMM'),(level - 1)),'yyyymm') as close_ym
                         from dual
                         connect by add_months(to_date(:start_woldo, 'YYYYMM'),(level - 1)) <= to_date(:end_woldo, 'YYYYMM')
                       )
	"""
	bind_arr = {"start_woldo":item.stdYear+"01", "end_woldo":item.stdYear+"12"}

	db.execute(qry , bind_arr)
	
	fields = db.get_field_names()
	datas = db.get_datas()

	close_yms = datas[0][0]+",999999"
	add_str = "PIVOT(sum(susuryo) FOR close_ym IN ("+close_yms+"))"

	if item.fc_code != "":
		qry = f"""with a1 as (select close_ym, gubun, sum(SUSURYO) SUSURYO
                                  from NEWINCAR.SUJI_SUMMARY
                                  where close_ym between :start_woldo and :end_woldo
                                  and fc_code = decode(:fc_code, null, fc_code, :fc_code)   --fc_code
                                  group by close_ym, gubun)
                           ,a as (select close_ym, gubun, sum(SUSURYO) SUSURYO
                                  from (select '999999' close_ym, gubun, SUSURYO
                                        from a1
                                        union all
                                        select close_ym, gubun, SUSURYO from a1
                                        )
                                  group by close_ym, gubun)
                      select *
                      from (select lpad('　　', n.tab_no*2)||n.code_name code_name
                                  ,decode(n.code_exp,'N',' ',n.code) code
                                  ,decode(n.code_exp,'N',' ','Y',' ',n.code_exp) code_exp
                                  ,n.order_no
                                  ,trim(n.code_doc) code_doc
                                  ,a.close_ym
                                  ,a.susuryo
                            from a
                                ,(select * from NEWINCAR.SUJI_CODE_NM where close_year = :close_year) n
                            where a.gubun (+)= n.code)
                      {add_str}
                      order by order_no 
		"""
		bind_arr = {
							"start_woldo":item.stdYear+"01"
						,	"end_woldo":item.stdYear+"12"
						,	"close_year":item.stdYear
						,	"fc_code":item.fc_code
					}
	else:
		qry = f"""with a1 as (select close_ym, gubun, sum(SUSURYO) SUSURYO
                                  from NEWINCAR.SUJI_SUMMARY_DEPT4
                                  where close_ym between :start_woldo and :end_woldo
                                  and dept_code1 = decode(:dept_code1, null, dept_code1, :dept_code1)   --detph1
                                  and dept_code2 = decode(:dept_code2, null, dept_code2, :dept_code2)   --detph2
                                  and dept_code3 = decode(:dept_code3, null, dept_code3, :dept_code3)   --detph3
                                  and dept_code4 = decode(:dept_code4, null, dept_code4, :dept_code4)   --detph4
                                  and dept_code5 = decode(:dept_code5, null, dept_code5, :dept_code5)   --detph5
                                  group by close_ym, gubun)
                           ,a as (select close_ym, gubun, sum(SUSURYO) SUSURYO
                                  from (select '999999' close_ym, gubun, SUSURYO
                                        from a1
                                        union all
                                        select close_ym, gubun, SUSURYO from a1
                                        )
                                  group by close_ym, gubun)
                      select *
                      from (select lpad('　　', n.tab_no*2)||n.code_name code_name
                                  ,decode(n.code_exp,'N',' ',n.code) code
                                  ,decode(n.code_exp,'N',' ','Y',' ',n.code_exp) code_exp
                                  ,n.order_no
                                  ,trim(n.code_doc) code_doc
                                  ,a.close_ym
                                  ,a.susuryo
                            from a
                                ,(select * from NEWINCAR.SUJI_CODE_NM where close_year = :close_year) n
                            where a.gubun (+)= n.code)
                      {add_str}
                      order by order_no
		"""
		bind_arr = {
							"start_woldo":item.stdYear+"01"
						,	"end_woldo":item.stdYear+"12"
						,	"close_year":item.stdYear
						,	"dept_code1":item.dept_code1
						,	"dept_code2":item.dept_code2
						,	"dept_code3":item.dept_code3
						,	"dept_code4":item.dept_code4
						,	"dept_code5":item.dept_code5
					}
	qry.replace("{add_str}", add_str)
	db.execute(qry , bind_arr)
	
	fields = db.get_field_names()
	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'
	
	items = [{field:value for field, value in zip(fields, data)} for data in datas]
	return items

class BohunsaInfoItem(BaseModel):
	bohumsaGb: str = None

@router.post("/bohumsaInfoList")
def getBohumsaInfoList(item: BohunsaInfoItem):
	db = DbLink()
	
	add_str=""
	if not item.bohumsaGb:
		add_str = " and b.gubun in ('3','4') "
	else:
		add_str = " and b.gubun in ('"+item.bohumsaGb+"') "
	qry = f"""select a.wonsusa_nm label, a.wonsusa_cd data
                  from wonsusa a
                     , bohumsa_code b
                  where a.wonsusa_cd = b.code
                  and a.use_yb = 1
                  {add_str}
                  and b.use_yb = 1 
	"""
	bind_arr={}
	db.execute(qry,bind_arr)
	
	fields = db.get_field_names()

	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'

	list_field =[]
	list_field = [zip (fields, data) for data in datas]
	
	items = [{field:value for field, value in zip(fields, data)} for data in datas]
	return items

class DeptInfoItem(BaseModel):
	level: str = None
	upcode: str = None

@router.post("/deptInfoList")
def getDeptInfoList(item: DeptInfoItem):
	db = DbLink()
	
	qry=""
	if item.level=="1":
		qry = """ select distinct dept_code1 code, dept_name1 name
                          from suji_dept@service
                          --where close_ym = to_char(add_months(sysdate,-1),'yyyymm')   --전월, 작업전 조회 불가로 변경함
                          where close_ym = (select max(close_ym) from suji_dept@service ) """
		bind_arr={}
	elif item.level=="2":
		qry = """ select distinct dept_code2 code, dept_name2 name
                          from suji_dept@service
                          --where close_ym = to_char(add_months(sysdate,-1),'yyyymm')   --전월, 작업전 조회 불가로 변경함
                          where close_ym = (select max(close_ym) from suji_dept@service )
                          and dept_code1 = decode(:upcode, null, dept_code1, :upcode) """
		bind_arr={"upcode":item.upcode}
	elif item.level=="3":
		qry = """ select distinct dept_code3 code, dept_name3 name
                          from suji_dept@service
                          --where close_ym = to_char(add_months(sysdate,-1),'yyyymm')   --전월, 작업전 조회 불가로 변경함
                          where close_ym = (select max(close_ym) from suji_dept@service )
                          and dept_code2 = decode(:upcode, null, dept_code2, :upcode) """
		bind_arr={"upcode":item.upcode}
	elif item.level=="4":
		qry = """ select distinct dept_code4 code, dept_name4 name
                          from suji_dept@service
                          --where close_ym = to_char(add_months(sysdate,-1),'yyyymm')   --전월, 작업전 조회 불가로 변경함
                          where close_ym = (select max(close_ym) from suji_dept@service )
                          and dept_code3 = decode(:upcode, null, dept_code3, :upcode) """
		bind_arr={"upcode":item.upcode}
	elif item.level=="5":
		qry = """ select distinct dept_code5 code, dept_name5 name
                          from suji_dept@service
                          --where close_ym = to_char(add_months(sysdate,-1),'yyyymm')   --전월, 작업전 조회 불가로 변경함
                          where close_ym = (select max(close_ym) from suji_dept@service )
                          and dept_code4 = decode(:upcode, null, dept_code4, :upcode) """
		bind_arr={"upcode":item.upcode}
	elif item.level=="9":
		qry = """ select * from
                          (select distinct fc_code code, fc_name||'('||fc_code||')'||(select decode(fire_date,null,null,'_퇴사') from sawon@service where sawon_cd =fc_code) name
                          from suji_dept@service
                          --where close_ym = to_char(add_months(sysdate,-1),'yyyymm')   --전월, 작업전 조회 불가로 변경함
                          where close_ym = (select max(close_ym) from suji_dept@service )
                          and dept_code4 = decode(:upcode, null, dept_code4, :upcode))
                          order by name """
		bind_arr={"upcode":item.upcode}
	elif item.level=="A":
		qry = """ select * from
                          (select distinct fc_code code, fc_name||'('||fc_code||')'||(select decode(fire_date,null,null,'_퇴사') from sawon@service where sawon_cd =fc_code) name
                          from suji_dept@service
                          --where close_ym = to_char(add_months(sysdate,-1),'yyyymm')   --전월, 작업전 조회 불가로 변경함
                          where close_ym = (select max(close_ym) from suji_dept@service )
                          and dept_code5 = decode(:upcode, null, dept_code5, :upcode))
                          order by name """
		bind_arr={"upcode":item.upcode}

	
	db.execute(qry,bind_arr)
	
	fields = db.get_field_names()

	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'

	list_field =[]
	list_field = [zip (fields, data) for data in datas]
	
	#items = [{field:value for field, value in zip(fields, data)} for data in datas]
	return list_field

class SawonInfoItem(BaseModel):
	keyword: str = None
	stdYear: str = None

@router.post("/sawonInfoList")
def getSawonInfoList(item: SawonInfoItem):
	db = DbLink()
	
	add_str=""

	qry = f"""select distinct dept_code1,dept_code2,dept_code3,dept_code4,dept_code5,fc_code
                         ,dept_name1,dept_name2,dept_name3,dept_name4,dept_name5,fc_name
                  from   suji_dept
                  where  substr(close_ym,1,4) = :close_year
                  and    fc_name like :keyword
                  order by fc_code
	"""
	bind_arr={"keyword":item.keyword+"%", "close_year":item.stdYear}
	db.execute(qry,bind_arr)
	
	fields = db.get_field_names()

	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'

	list_field =[]
	list_field = [zip (fields, data) for data in datas]
	
	#items = [{field:value for field, value in zip(fields, data)} for data in datas]
	return list_field

@router.post("/suikDetailInit")
def getSawonInfoList():
	db = DbLink()

	qry = f"""select '전체' label, '' data
                  from dual
                  union all
                  select '생명' label, '4' data
                  from dual
                  union all
                  select '화재' label, '3' data
                  from dual 
	"""
	bind_arr={}
	db.execute(qry,bind_arr)
	
	fields = db.get_field_names()

	datas = db.get_datas()

	if not datas:
		return 'NoData'
	
	list_field =[]
	#list_field = {'wonsusaGblist' : [zip (fields, data) for data in datas]}
	#list_field['wonsusaGblist'] = {zip (fields, data) for data in datas}
	list_field.append({"wonsusaGblist":[zip (fields, data) for data in datas]})


	qry = """select '전체' label, '' data
                  from dual
                  union all
                  select to_char(code) label, code_name data
                  from suji_code_nm
                  where close_year = to_char(sysdate,'yyyy')
                  and   code_exp in ('Y','N')
	"""
	bind_arr={}
	db.execute(qry,bind_arr)
	
	fields = db.get_field_names()

	datas = db.get_datas()

	if not datas:
		return 'NoData'

	list_field.append({"codelist":[zip (fields, data) for data in datas]})

	#list_field = {'codelist' : [zip (fields, data) for data in datas]}
	#list_field['codelist'] = {zip (fields, data) for data in datas}

	qry = f"""select max(close_ym) last_close_ym
                  from SUJI_SUMMARY
	"""
	bind_arr={}
	db.execute(qry,bind_arr)
	
	fields = db.get_field_names()

	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'

	#list_field = {'last_close_ym' : [zip (fields, data) for data in datas]}
	#list_field['last_close_ym'] = {zip (fields, data) for data in datas}
	list_field.append({"last_close_ym":''.join(datas[0])})
	#items = [{field:value for field, value in zip(fields, data)} for data in datas]
	return list_field

class SuikDetailListItem(BaseModel):
	stdCloseYmS: str = None
	stdCloseYmE: str = None
	stdGubun: str = None
	stdBohumsaGb: str = None
	stdWonsusaCd: str = None
	dept_code1: str = None
	dept_code2: str = None
	dept_code3: str = None
	dept_code4: str = None
	dept_code5: str = None
	fc_code: str = None
	viewGubun: str = None
	currentPageNo: str = None
	listCount: str = None

@router.post("/suikDetailList")
def getSawonInfoList(item:SuikDetailListItem):
	db = DbLink()

	if not item.stdBohumsaGb:
		add_tbl_bohumjoin_str = "";
		add_tbl_bohumsel_str = "";
	else:
		add_tbl_bohumjoin_str = " ,bohumsa_code c"
		if not item.stdWonsusaCd:
			add_tbl_bohumsel_str =" and c.code = a.wonsusa_cd   and c.gubun in (3, 4)"
		else:
			add_tbl_bohumsel_str = f"and c.code = a.wonsusa_cd   and c.gubun in ({item.stdBohumsaGb})"

	add_tbl_deptjoin_str=""
	add_tbl_deptsel_str=""
	if item.dept_code1 or item.dept_code2 or item.dept_code3 or item.dept_code4 or item.dept_code5 or item.fc_code:
		add_tbl_deptjoin_str = " ,NEWINCAR.SUJI_DEPT b "
		add_tbl_deptsel_str = f""" and a.close_ym = b.close_ym
                  and a.fc_code = b.fc_code
                  and b.dept_code1 = decode({item.dept_code1}, null, b.dept_code1, {item.dept_code1})
                  and b.dept_code2 = decode({item.dept_code2}, null, b.dept_code2, {item.dept_code2})
                  and b.dept_code3 = decode({item.dept_code3}, null, b.dept_code3, {item.dept_code3})
                  and b.dept_code4 = decode({item.dept_code4}, null, b.dept_code4, {item.dept_code4})
                  and b.dept_code5 = decode({item.dept_code5}, null, b.dept_code5, {item.dept_code5}) """



	inner_query = f"""with a as (select /*+ ORDERED */
                                    a.close_ym
                                   ,a.gubun
                                   ,(select code_name from NEWINCAR.SUJI_CODE_NM where CLOSE_YEAR = substr(a.close_ym,1,4) and code = a.gubun) code_name
                                   ,(select wonsusa_nm from WONSUSA@service where wonsusa_cd = a.wonsusa_cd) wonsusa_nm
                                   ,a.JGNO
                                   ,a.sangpum_cd
                                   ,a.wonsusa_cd
                                   ,a.statuscode_cd
                                   ,case a.sangpum_cd
                                         when '1' then '자동차(개인)'
                                         when '2' then '자동차(업무)'
                                         when '3' then '자동차(개인+)'
                                         when '4' then '자동차(업무+)'
                                         when '5' then '자동차(영업)'
                                         when '6' then '자동차(이륜)'
                                         when '7' then '자동차(기타)'
                                    else (select name from SANGPUM@service where code = a.sangpum_cd) end sangpum_nm
                                   ,decode(a.statuscode_cd,' ',' ',(select sub_nm from commcode@service where root_nm ='수지구분' and sub_cd = a.statuscode_cd)||'('||a.statuscode_cd||')') statuscode_nm
                                   ,a.susuryo
                                   ,a.fc_code
                             from NEWINCAR.SUJI_CONTRACT a
                             {add_tbl_deptjoin_str}
                             {add_tbl_bohumjoin_str}
                             where a.close_ym between :stdCloseYmS and :stdCloseYmE
                               and a.gubun      = decode(:stdGubun, null, a.gubun, :stdGubun)
                               and a.wonsusa_cd = decode(:stdWonsusaCd, null, a.wonsusa_cd, :stdWonsusaCd)
                               and a.fc_code    = decode(:fc_code, null, a.fc_code, :fc_code)
                               {add_tbl_deptsel_str}
                               {add_tbl_bohumsel_str}
                             )
                  select /*+ ORDERED USE_NL(a b) */
                         a.close_ym, a.gubun, a.code_name, a.wonsusa_nm, a.jgno, a.sangpum_nm, a.statuscode_nm, a.susuryo, a.fc_code
                        ,decode(b.fc_name,'','전체',b.dept_name1 || '>' || b.dept_name2 || '>' || b.dept_name3 || '>' || b.dept_name4 || '>' || b.dept_name5 || '>' || b.fc_name) dept_nm
                  from a
                     , NEWINCAR.SUJI_DEPT b
                  where a.close_ym = b.close_ym(+)
                  and a.fc_code = b.fc_code(+)
                  order by a.close_ym, a.gubun, a.wonsusa_cd, a.jgno, a.sangpum_cd, a.statuscode_cd, a.fc_code
	"""
	bind_arr={"stdCloseYmS":item.stdCloseYmS
					, "stdCloseYmE":item.stdCloseYmE
					, "stdGubun":item.stdGubun
					, "stdWonsusaCd":item.stdWonsusaCd
					, "fc_code":item.fc_code}

	query = f"""select count(*) as total
                  from (
                    {inner_query}
                  ) """
	db.execute(query,bind_arr)
	
	fields = db.get_field_names()

	datas = db.get_datas()

	if not datas:
		return 'NoData'
	
	list_field =[]
	#list_field['total_records'] = {zip (fields, data) for data in datas}
	total_records = ''.join(map(str,datas[0]))
	list_field.append({"total_records":total_records})

	total_pages =1
	if int(total_records)>0:
		total_pages = math.ceil(int(total_records)/int(item.listCount))

	list_field.append({"total_pages" : total_pages});
	
	#items = [{field:value for field, value in zip(fields, data)} for data in datas]

	if total_records:
		start_row = (int(item.currentPageNo) - 1) * int(item.listCount)
		end_row = start_row + int(item.listCount)

		if item.viewGubun == '1':
			start_row = 0
			end_row = int(total_records)
		

		query = f"""
				  select x.* from (
				  select x.*, rownum as r from (
					  {inner_query}
					) x
					where rownum <= :end_row
				  ) x
				  where x.r > :start_row
				  and   x.r <= :end_row
					"""
		bind_arr["start_row"] =start_row
		bind_arr["end_row"] =end_row
		
		#bind_arr.append({"currPageNo": item.currPageNo})
		#bind_arr.append({"listCount": item.listCount})

		db.execute(query,bind_arr)
	
		fields = db.get_field_names()

		datas = db.get_datas()

		if not datas:
			return 'NoData'


		list_field.append({"list":[zip (fields, data) for data in datas]})
	

	return list_field

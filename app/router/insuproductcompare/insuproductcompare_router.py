# -*- coding: utf-8 -*-
from fastapi import APIRouter
from app.database.testorcl import TestOrcl
from pydantic import BaseModel
import math

router = APIRouter(
    prefix="/api/insuproductcompare",
)

class WonsusaListItem(BaseModel):
	inscoNm: str = None

@router.post("/getWonsusaList")
def wonsusa_list(item: WonsusaListItem):
	db = TestOrcl()

	qry = """
			select		insco_cd
					,	insco_nm
			from        insu_product_compare_wonsusa
			where       insco_nm like :insco_nm
			order by insco_nm asc
	"""
	bind_arr = {"insco_nm":"%"+item.inscoNm+"%"}

	db.execute(qry , bind_arr)
	
	fields = db.get_field_names()
	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'
	
	items = [{field:value for field, value in zip(fields, data)} for data in datas]
	return items

class CategoryListItem(BaseModel):
	categoryGrp: str = None

@router.post("/getCategoryList")
def category_list(item: CategoryListItem):
	db = TestOrcl()

	qry = """
			select		category_val
					,	category_nm
			from        insu_product_compare_category
			where       category_grp = :category_grp
			order by category_val asc
	"""
	bind_arr = {"category_grp":item.categoryGrp}

	db.execute(qry , bind_arr)
	
	fields = db.get_field_names()
	datas = db.get_datas()

	db.close()

	if not datas:
		return 'NoData'
	
	items = [{field:value for field, value in zip(fields, data)} for data in datas]
	return items

# Copyright (c) 2022, 254 ERP and contributors
# For license information, please see license.txt

import frappe,json
from frappe.model.document import Document

class Production(Document):

	@frappe.whitelist()
	def get_required_raw_materials(self):
		"""
		Gets required raw materials based on BOM and Qty
		"""
		print("*"*80)
		# get required items based on BOM and Qty
		raw_materials = get_items_list_given_bom_n_qty(self.select_bom,self.qty,self.uom)
		if not raw_materials.get('status'):
			return raw_materials
	
		# clear the table before re-appending
		self.required_materials_table = []
		# now add the items to the table
		for item in raw_materials.get('value'):
			# determine the amount available in the warehouse
			stock_result = get_bin_details_twb(self.source_warehouse,item.get('bom_item'))
			if len(stock_result):
				available_stock = stock_result[0].get('actual_qty')
				# now append the correct items and quatities
				self.append(
					"required_materials_table",
					{
						"item": item.get('bom_item'),
						"stock_qty": available_stock,
						"required_qty": item.get('qty'),
						"qty_shortage": available_stock - item.get('qty') * -1 if (available_stock - item.get('qty')) < 0 else 0
					}
				)
			else:
				self.append(
					"required_materials_table",
					{
						"item": item.get('bom_item'),
						"stock_qty": 0,
						"required_qty": item.get('qty'),
						"qty_shortage": item.get('qty') * -1
					}
				)
		
		# return true to end execuation
		return {'status':True}


def get_items_list_given_bom_n_qty(bom_name,qty,uom):
	'''
	Function that returns items list given bom_name and 
	qty
	input:
		str - bom_name
		qty - int
	output:
		list - dough_list (with items and qty)
	'''
	# get BOM document
	bom_doc = frappe.get_doc("BOM",bom_name)
	# get all the dough items required for this BOM
	bom_items_list = bom_doc.items
	if not len(bom_items_list):
		return {
			'status': False,
			'message':"Materials not defined for BOM:'{}'".format(bom_name)
		}
	
	# find conversion factor from given qty to stock qty
	bom_uom_conversion = frappe.get_list("UOM Conversion Factor",
			filters={
				'from_uom':uom,
				'to_uom': bom_doc.uom
			},
			fields=['name', 'value']
		)

	if not len(bom_uom_conversion):
		return {
			'status': False,
			'message':"A conversion factor from '{}' to '{}'".format(uom,bom_name)
		}
	
	# conversion factor from the UOM indicated in Production to BOM UoM
	conversion_factor_value = bom_uom_conversion[0].get('value')	

	# determine share ratio assumign we are using Kgs only
	total_items_qty = sum([x.qty for x in bom_items_list])

	items_list = [] #initialize as empty
	for bom_item in bom_items_list: 
		items_list.append({ 
			'bom_item':bom_item.item_code,
			'qty': (bom_item.qty / total_items_qty) * qty * conversion_factor_value
		})
	# return the full dough list
	return {
		'status': True,
		'value': items_list
	}
	

@frappe.whitelist()
def get_bin_details_twb(warehouse, item_code):
    '''
    Function that determines the stock balance of an item in the warehouses
    '''
    # format the sql query here
    sql_string = """ select ifnull(sum(projected_qty),0) as projected_qty,
        ifnull(sum(actual_qty),0) as actual_qty, ifnull(sum(ordered_qty),0) as ordered_qty,
        ifnull(sum(reserved_qty_for_production),0) as reserved_qty_for_production, warehouse,
        ifnull(sum(planned_qty),0) as planned_qty
        from `tabBin` where item_code = '{}' and warehouse = '{}' group by item_code, warehouse
    """.format(item_code, warehouse)
    # return the result of the query as a dictionary
    return frappe.db.sql(sql_string, as_dict=1,)
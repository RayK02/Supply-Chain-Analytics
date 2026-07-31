from __future__ import annotations

import base64, io, re
from datetime import date, datetime
from typing import Any
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from app.inventory_analysis import calculate_analysis
from app.inventory_utils import DEFAULT_PARAMETERS, as_float, normalize_article_key, parse_code_set

SHEETS={"sales":"Artikelposten","articles":"Artikel_Stamm","current":"Lagerhaltungsdaten_IST","vpe":"VPE","params":"Parameter"}
ALIASES={
"article":["Artikelnummer","Artikelnr.","Artikelnr","Artikel-Nr.","Nr.","Nr","Item No."],
"description":["Beschreibung","Artikelbeschreibung","Description"],
"date":["Buchungsdatum","Posting Date","Datum"],"type":["Belegart","Document Type"],"qty":["Menge","Quantity"],
"location":["Lagerortcode","Lagerort","Location Code"],"vpe":["VPE","Verpackungseinheit","Menge je VPE"],
"minimum":["Mindestbestand","Minimum Inventory","Sicherheitsbestand"],"order":["Bestellmenge","Order Quantity","Bestelllosgröße"],
"maximum":["Maximalbestand","Maximum Inventory"]}

def canon(v:Any)->str:
 t=str(v or "").strip().lower().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
 return re.sub(r"[^a-z0-9]+","",t)

def sheet(wb,name:str,required=True):
 found={canon(x):x for x in wb.sheetnames}.get(canon(name))
 if not found and required: raise ValueError(f"Tabellenblatt fehlt: {name}")
 return found

def rows(wb,name:str):
 ws=wb[name]; it=ws.iter_rows(values_only=True)
 try: raw=next(it)
 except StopIteration:return [],[]
 headers=[str(x).strip() if x is not None else f"Spalte_{i+1}" for i,x in enumerate(raw)]
 return headers,[{headers[i]:(r[i] if i<len(r) else None) for i in range(len(headers))} for r in it if any(x not in (None,"") for x in r)]

def col(headers,key,required=True):
 by={canon(x):x for x in headers}
 for alias in ALIASES[key]:
  if canon(alias) in by:return by[canon(alias)]
 for alias in ALIASES[key]:
  a=canon(alias)
  for k,v in by.items():
   if a in k or k in a:return v
 if required:raise ValueError(f"Spalte fehlt: {ALIASES[key][0]}")
 return None

def as_date(v):
 if isinstance(v,datetime):return v.date()
 if isinstance(v,date):return v
 if isinstance(v,str):
  for fmt in ("%d.%m.%Y","%Y-%m-%d","%d/%m/%Y"):
   try:return datetime.strptime(v.strip(),fmt).date()
   except ValueError:pass
 return None

def params(wb):
 out=dict(DEFAULT_PARAMETERS); name=sheet(wb,SHEETS["params"],False)
 if not name:return out
 mapping={"belegart":"document_type","monate":"months_average","abcagrenze":"abc_a_threshold","abcbgrenze":"abc_b_threshold","xyzxgrenze":"xyz_x_threshold","xyzygrenze":"xyz_y_threshold","mindestfaktora":"minimum_factor_a","mindestfaktorb":"minimum_factor_b","mindestfaktorc":"minimum_factor_c","bestellintervalla":"order_interval_a","bestellintervallb":"order_interval_b","bestellintervallc":"order_interval_c","automatischelagerorte":"automatic_locations","manuellelagerorte":"manual_locations"}
 for r in wb[name].iter_rows(values_only=True):
  if not r or r[0] in (None,""):continue
  key=mapping.get(canon(r[0])); value=r[1] if len(r)>1 else None
  if key:out[key]=str(value).strip() if key in {"document_type","automatic_locations","manual_locations"} else (as_float(value) if as_float(value) is not None else out[key])
 return out

def article_names(wb):
 name=sheet(wb,SHEETS["articles"],False)
 if not name:return {}
 h,rs=rows(wb,name); a=col(h,"article"); d=col(h,"description",False); out={}
 for r in rs:
  k=normalize_article_key(r.get(a))
  if k:out[k]=str(r.get(d) or "").strip() if d else ""
 return out

def vpe_values(wb):
 name=sheet(wb,SHEETS["vpe"],False)
 if not name:return {}
 h,rs=rows(wb,name); a=col(h,"article"); v=col(h,"vpe"); out={}
 for r in rs:
  k=normalize_article_key(r.get(a)); n=as_float(r.get(v))
  if k and n and n>0:out[k]=n
 return out

def current_values(wb,p):
 name=sheet(wb,SHEETS["current"],False)
 if not name:return {}
 h,rs=rows(wb,name); a=col(h,"article"); l=col(h,"location",False); m=col(h,"minimum",False); o=col(h,"order",False); x=col(h,"maximum",False)
 automatic=parse_code_set(p.get("automatic_locations")); manual=parse_code_set(p.get("manual_locations")); out={}
 for r in rs:
  k=normalize_article_key(r.get(a)); loc=str(r.get(l) or "").strip().upper() if l else ""
  if not k:continue
  priority=0 if loc in automatic else (1 if loc in manual else 2)
  value={"location":loc,"manual_review":loc in manual,"minimum_stock_current":as_float(r.get(m)) if m else None,"order_quantity_current":as_float(r.get(o)) if o else None,"maximum_stock_current":as_float(r.get(x)) if x else None,"priority":priority}
  if k not in out or priority<out[k]["priority"]:out[k]=value
 for v in out.values():v.pop("priority",None)
 return out

def sales_values(wb,p):
 h,rs=rows(wb,sheet(wb,SHEETS["sales"])); a=col(h,"article"); d=col(h,"description",False); dt=col(h,"date"); typ=col(h,"type"); q=col(h,"qty")
 out=[]; names={}
 for r in rs:
  k=normalize_article_key(r.get(a)); day=as_date(r.get(dt)); qty=as_float(r.get(q)); desc=str(r.get(d) or "").strip() if d else ""
  if k and desc:names.setdefault(k,desc)
  if k and day and qty is not None:out.append({"article_key":k,"description":desc,"booking_date":day,"document_type":str(r.get(typ) or "").strip(),"quantity":qty})
 return out,names

def compare(current,proposed):
 if current is None or proposed is None:return "unknown",None
 delta=float(proposed)-float(current)
 return ("ok" if abs(delta)<1e-9 else "increase" if delta>0 else "decrease"),delta

def analyse_workbook(file_object):
 wb=load_workbook(file_object,data_only=True,read_only=True); p=params(wb); names=article_names(wb); vpes=vpe_values(wb); current=current_values(wb,p); sales,sales_names=sales_values(wb,p); names={**sales_names,**names}
 results,meta=calculate_analysis(sales,names,vpes,p)
 for r in results:
  cur=current.get(r["article_key"],{}); r.update({"location":cur.get("location",""),"manual_review":bool(cur.get("manual_review")),"minimum_stock_current":cur.get("minimum_stock_current"),"order_quantity_current":cur.get("order_quantity_current"),"maximum_stock_current":cur.get("maximum_stock_current")})
  r["minimum_stock_status"],r["minimum_stock_delta"]=compare(r["minimum_stock_current"],r["minimum_stock"])
  r["order_quantity_status"],r["order_quantity_delta"]=compare(r["order_quantity_current"],r["order_quantity"])
  r["xyz_class"]=r["xyz_class"] or "–"; r["abcxyz"]=r["abcxyz"] or f'{r["abc_class"]}–'
  r["overall_status"]="manual" if r["manual_review"] else ("ok" if r["minimum_stock_status"]=="ok" and r["order_quantity_status"]=="ok" else "change")
 if not results:raise ValueError("Keine auswertbaren Verkaufsabgänge gefunden.")
 meta["parameters"]=p; return sorted(results,key=lambda r:(-r["sales_total"],r["article_key"])),meta

EXPORT=[("article_key","Artikelnummer"),("description","Beschreibung"),("abc_class","ABC"),("xyz_class","XYZ"),("abcxyz","ABCXYZ"),("sales_total","Absatz gesamt"),("average_month","Ø Absatz/Monat"),("minimum_stock","Mindestbestand Vorschlag"),("minimum_stock_current","Mindestbestand IST"),("minimum_stock_delta","Delta Mindestbestand"),("weekly_need","Wochenbedarf"),("order_interval","Bestellintervall Wochen"),("vpe","VPE"),("order_quantity","Bestellmenge Vorschlag"),("order_quantity_current","Bestellmenge IST"),("order_quantity_delta","Delta Bestellmenge"),("location","Lagerort"),("overall_status","Status")]
def build_export(results,meta):
 wb=Workbook(); ws=wb.active; ws.title="ABC_Analyse"; ws.append([v for _,v in EXPORT])
 for r in results:ws.append([r.get(k) for k,_ in EXPORT])
 ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
 sm=wb.create_sheet("Zusammenfassung");sm.append(["Kennzahl","Wert"]);sm.append(["Stichtag",meta.get("stichtag")]);sm.append(["Gesamtabsatz",meta.get("overall_sales")])
 for k,v in sorted((meta.get("counts") or {}).items()):sm.append([f"Anzahl {k}",v])
 pa=wb.create_sheet("Parameter");pa.append(["Parameter","Wert"])
 for k,v in (meta.get("parameters") or {}).items():pa.append([k,v])
 fill=PatternFill("solid",fgColor="1F4E78");font=Font(color="FFFFFF",bold=True)
 for sh in wb.worksheets:
  for c in sh[1]:c.fill=fill;c.font=font
  for cells in sh.columns:sh.column_dimensions[get_column_letter(cells[0].column)].width=min(max(max(len(str(c.value or "")) for c in cells)+2,10),38)
 out=io.BytesIO();wb.save(out);return out.getvalue()
def export_data_uri(results,meta):return "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,"+base64.b64encode(build_export(results,meta)).decode("ascii")
